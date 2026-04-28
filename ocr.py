import tkinter as tk
from tkinter import ttk, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk, ImageGrab, ImageDraw
import pyperclip
import io
import sys
from paddleocr import PaddleOCR
import re
import numpy as np
import tempfile
import os

class PaddleOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PaddleOCR Image to Text Tool")
        self.root.geometry("900x700")
        
        # Store the current image and OCR results
        self.current_image = None
        self.annotated_image = None
        self.ocr_model = None
        self.current_ocr_result = None
        self.raw_ocr_text = None  # Stores the original full OCR text (unformatted)

        # Output type for formatting (tweet, tweet thread, etc.)
        self.output_type_var = tk.StringVar(value="tweet")

        # Language options
        self.languages = {
            "Chinese (Simplified)": "ch",
            "English": "en",
            "Japanese": "japan",
            "Korean": "korean",
            "French": "fr",
            "German": "german"
        }
        
        self.setup_ui()
        self.setup_bindings()
        self.init_ocr_model()
        
        self.last_clipboard_image_hash = None
        self.clipboard_monitor_running = False

        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top control bar
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Language selection
        ttk.Label(control_frame, text="OCR Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.lang_var = tk.StringVar(value="English")
        lang_combo = ttk.Combobox(control_frame, textvariable=self.lang_var, 
                                   values=list(self.languages.keys()), state="readonly", width=20)
        lang_combo.pack(side=tk.LEFT, padx=(0, 10))
        lang_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        # Instructions label
        instruction_text = "📋 Press Ctrl+V, or Drag & Drop an image file\n"
        instruction_text += "🖼️ Supports: PNG, JPEG, BMP, GIF | Built-in PaddleOCR engine"
        instructions = ttk.Label(control_frame, text=instruction_text, foreground='gray')
        instructions.pack(side=tk.LEFT, padx=(10, 0))
        
        self.auto_clipboard_var = tk.BooleanVar(value=False)
        self.auto_clipboard_cb = ttk.Checkbutton(control_frame, text="Auto-paste from clipboard", 
                                                 variable=self.auto_clipboard_var,
                                                 command=self.toggle_clipboard_monitor)
        self.auto_clipboard_cb.pack(side=tk.LEFT, padx=(10, 0))
        
        self.auto_process_var = tk.BooleanVar(value=False)
        self.auto_process_cb = ttk.Checkbutton(control_frame, text="Auto-process image", 
                                                 variable=self.auto_process_var)
        self.auto_process_cb.pack(side=tk.LEFT, padx=(10, 0))

        # Output type selection
        ttk.Label(control_frame, text="Output:").pack(
            side=tk.LEFT, padx=(10, 5)
        )
        self.output_type_var = tk.StringVar(value="tweet")
        output_combo = ttk.Combobox(
            control_frame,
            textvariable=self.output_type_var,
            values=[
                "tweet",
                "tweet thread",
                "quote retweet",
                "reddit post",
                "reddit comment",
                "reddit thread",
            ],
            state="readonly",
            width=14,
        )
        output_combo.pack(side=tk.LEFT, padx=(0, 5))
        output_combo.bind("<<ComboboxSelected>>", self.on_output_type_change)

        # Paned window for split view
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left frame for image display
        self.image_frame = ttk.LabelFrame(paned, text="Image Preview", padding="5")
        paned.add(self.image_frame, weight=1)
        
        # Image label
        self.image_label = ttk.Label(self.image_frame, text="No image pasted yet\n\nPress Ctrl+V to paste an image")
        self.image_label.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        # Right frame for text output
        self.text_frame = ttk.LabelFrame(paned, text="Extracted Text", padding="5")
        paned.add(self.text_frame, weight=1)
        
        # Text widget with scrollbar
        text_container = ttk.Frame(self.text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)
        
        self.text_widget = tk.Text(text_container, wrap=tk.WORD, font=('Arial', 10))
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.copy_button = ttk.Button(button_frame, text="📋 Copy to Clipboard", 
                                       command=self.copy_to_clipboard, state='disabled')
        self.copy_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="🗑️ Clear All", 
                                        command=self.clear_all)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        self.process_button = ttk.Button(button_frame, text="🔍 Process Image (OCR)", 
                                          command=self.process_image, state='disabled')
        self.process_button.pack(side=tk.LEFT, padx=5)
        
        # Confidence filter
        ttk.Label(button_frame, text="Min Confidence:").pack(side=tk.LEFT, padx=(20, 5))
        self.confidence_var = tk.DoubleVar(value=0.5)
        confidence_scale = ttk.Scale(button_frame, from_=0.0, to=1.0, variable=self.confidence_var,
                                      orient=tk.HORIZONTAL, length=100)
        confidence_scale.pack(side=tk.LEFT, padx=(0, 5))
        self.confidence_label = ttk.Label(button_frame, text="0.5")
        self.confidence_label.pack(side=tk.LEFT)
        confidence_scale.configure(command=self.update_confidence_label)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Press Ctrl+V to paste an image")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))
        
    def update_confidence_label(self, value):
        """Update confidence label when slider moves"""
        # Fixed: Use config() instead of setText()
        self.confidence_label.config(text=f"{float(value):.2f}")
        
    def setup_bindings(self):
        # Bind Ctrl+V to paste from clipboard
        self.root.bind('<Control-v>', self.paste_from_clipboard)
        
        # Setup Drag and Drop
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        
        # Setup hover events for image_label
        self.image_label.bind('<Enter>', self.show_full_image)
        self.image_label.bind('<Leave>', self.hide_full_image)

    def show_full_image(self, event):
        img_source = self.annotated_image if getattr(self, 'annotated_image', None) else self.current_image
        if img_source is None:
            return
            
        self.hover_window = tk.Toplevel(self.root)
        self.hover_window.overrideredirect(True)
        
        x = event.x_root + 15
        y = event.y_root + 15
        
        # Ensure it fits on screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        img_w, img_h = img_source.size
        scale = min((screen_w - x - 20) / img_w, (screen_h - y - 20) / img_h, 1.0)
        
        if scale < 1.0:
            new_size = (int(img_w * scale), int(img_h * scale))
            img_to_show = img_source.resize(new_size, Image.Resampling.LANCZOS)
        else:
            img_to_show = img_source
            
        photo = ImageTk.PhotoImage(img_to_show)
        label = ttk.Label(self.hover_window, image=photo, borderwidth=2, relief="solid")
        label.image = photo
        label.pack()
        self.hover_window.geometry(f"+{x}+{y}")

    def hide_full_image(self, event):
        if hasattr(self, 'hover_window') and self.hover_window:
            self.hover_window.destroy()
            self.hover_window = None

    def handle_drop(self, event):
        file_path = event.data
        # tkinterdnd2 sometimes wraps paths in curly braces if they contain spaces
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        
        try:
            img = Image.open(file_path)
            img.load()  # Ensure it's fully loaded
            self.current_image = img
            self.annotated_image = None
            self.display_image(self.current_image)
            self.status_var.set(f"Image loaded from file. Click 'Process Image' to extract text")
            self.process_button.config(state='normal')
            self.clear_button.config(state='normal')
            if self.auto_process_var.get():
                self.root.after(100, self.process_image)
        except Exception as e:
            self.status_var.set(f"Error loading image from drop: {str(e)}")
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")

    def toggle_clipboard_monitor(self):
        if self.auto_clipboard_var.get():
            self.clipboard_monitor_running = True
            try:
                clip_img = ImageGrab.grabclipboard()
                if isinstance(clip_img, Image.Image):
                    self.last_clipboard_image_hash = hash(clip_img.tobytes())
            except Exception:
                pass
            self.monitor_clipboard()
        else:
            self.clipboard_monitor_running = False

    def monitor_clipboard(self):
        if not self.clipboard_monitor_running:
            return
        
        try:
            clip_img = ImageGrab.grabclipboard()
            if isinstance(clip_img, Image.Image):
                img_hash = hash(clip_img.tobytes())
                if img_hash != self.last_clipboard_image_hash:
                    self.last_clipboard_image_hash = img_hash
                    self.current_image = clip_img
                    self.annotated_image = None
                    self.display_image(self.current_image)
                    self.status_var.set("Image auto-pasted from clipboard! Click 'Process Image'")
                    self.process_button.config(state='normal')
                    self.clear_button.config(state='normal')
                    if self.auto_process_var.get():
                        self.root.after(100, self.process_image)
        except Exception:
            pass
            
        if self.clipboard_monitor_running:
            self.root.after(1000, self.monitor_clipboard)
        
    def init_ocr_model(self):
        """Initialize PaddleOCR model - runs once at startup"""
        try:
            self.status_var.set("Initializing PaddleOCR model (first time may take a moment)...")
            self.root.update()
            
            # Get selected language code
            lang_code = self.languages[self.lang_var.get()]
            
            # Initialize PaddleOCR
            # use_angle_cls=True enables text direction classification for better accuracy
            self.ocr_model = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
                lang=lang_code)
            self.status_var.set(f"PaddleOCR ready - Language: {self.lang_var.get()}")
            
        except Exception as e:
            self.status_var.set(f"Failed to initialize PaddleOCR: {str(e)}")
            messagebox.showerror("Init Error", 
                               f"Failed to initialize PaddleOCR.\n\n"
                               f"Make sure you have installed:\n"
                               f"pip install paddlepaddle paddleocr\n\n"
                               f"Error: {str(e)}")
    
    def on_language_change(self, event=None):
        """Reinitialize OCR model when language changes"""
        if self.ocr_model:
            self.init_ocr_model()

    # ---------------------------------------------------------------------------
    #  Paragraph detection helpers (imported from deepseektest.py)
    # ---------------------------------------------------------------------------

    def is_bullet_point(self, text):
        """
        Check if text starts with a bullet point marker.
        Supports: -, *, •, ○, ▪, numbers (1., 2.), letters (a., b.), etc.
        """
        if not text or not text.strip():
            return False
        
        text_stripped = text.lstrip()
        
        # Common bullet point patterns
        bullet_patterns = [
            r'^[-*•○▪►→]',           # Common bullet symbols
            r'^\d+[\.\)]',            # Numbered lists: 1., 2., 1), 2)
            r'^[a-zA-Z][\.\)]',       # Letter lists: a., b., a), b)
            r'^[ivxIVX]+[\.\)]',      # Roman numerals: i., ii., iii.
            r'^[\u2022\u2023\u25E6\u2043\u2219]',  # Unicode bullets
        ]
        
        for pattern in bullet_patterns:
            if re.match(pattern, text_stripped):
                return True
        
        return False

    def detect_list_blocks(self, texts, start_index):
        """
        Detect a consecutive sequence of bullet points starting from start_index.
        Returns the end index of the list (exclusive) or None if not a list.
        """
        if not texts or start_index >= len(texts):
            return None
        
        # Check if current block is a bullet point
        if not self.is_bullet_point(texts[start_index]):
            return None
        
        # Find consecutive bullet points
        end_index = start_index + 1
        while end_index < len(texts) and self.is_bullet_point(texts[end_index]):
            end_index += 1
        
        # Return the range if we have at least 2 bullet points or if it's the only one
        # but we still want to treat single bullet points as lists
        return end_index if end_index > start_index else None

    def detect_paragraph_breaks(self, rec_boxes, texts, line_height_ratio=0.5):
        """
        Detect whether blocks belong to same paragraph or new paragraph.
        Special handling for bullet points to keep them on separate lines.
        
        Args:
            rec_boxes: List of [x1, y1, x2, y2] coordinates
            texts: List of recognized text strings
            line_height_ratio: Threshold for considering vertical gap as paragraph break
        
        Returns:
            List of integers: 0 = same line (space), 1 = new paragraph (newline),
                             2 = extra new paragraph (double newline)
        """
        if not rec_boxes or len(rec_boxes) == 0:
            return [1]
        
        # Result codes:
        # 0: Same line/paragraph - join with space
        # 1: New paragraph - join with newline
        # 2: Extra new paragraph - join with double newline
        
        result = [1]  # First block always starts a new paragraph
        
        for i in range(1, len(rec_boxes)):
            prev_box = rec_boxes[i-1]
            curr_box = rec_boxes[i]
            prev_text = texts[i-1]
            curr_text = texts[i]
            
            # Check if previous block ends with a Twitter timestamp
            if self.has_twitter_timestamp(prev_text):
                # Force a new paragraph (double newline for separation)
                result.append(2)  # Double newline
                continue
            
            # Check if current block is part of a list
            if self.is_bullet_point(curr_text):
                # Bullet points always get a newline (or double newline based on gap)
                prev_bottom = prev_box[3]
                curr_top = curr_box[1]
                vertical_gap = curr_top - prev_bottom
                curr_height = curr_box[3] - curr_box[1]
                
                # Check if gap is as wide or wider than current block height
                if vertical_gap >= curr_height:
                    result.append(2)  # Double newline for large gaps
                else:
                    result.append(1)  # Single newline for bullet points
                continue
            
            # Normal (non-list) paragraph detection logic
            prev_bottom = prev_box[3]  # y2
            curr_top = curr_box[1]     # y1
            
            # Calculate heights
            prev_height = prev_box[3] - prev_box[1]
            curr_height = curr_box[3] - curr_box[1]
            
            # Calculate vertical gap
            vertical_gap = curr_top - prev_bottom
            
            # Check horizontal overlap (same line/paragraph)
            x_overlap = min(prev_box[2], curr_box[2]) - max(prev_box[0], curr_box[0])
            
            # Determine if same line (horizontal arrangement)
            same_line = abs(curr_top - prev_bottom) < prev_height * 0.3 and x_overlap > 0
            
            if same_line:
                # Same line - definitely same paragraph
                result.append(0)  # Space
            else:
                # Different lines - check the gap size
                # If gap is as wide or wider than current block height, use double newline
                if vertical_gap >= curr_height:
                    result.append(2)  # Double newline
                elif vertical_gap > prev_height * (line_height_ratio + 1):
                    result.append(1)  # Regular new paragraph
                else:
                    result.append(0)  # Same paragraph (but different line - should be space)
        
        return result

    def group_into_paragraphs(self, texts, rec_boxes):
        """
        Group text blocks into paragraphs based on coordinate analysis.
        Special handling for lists to ensure each bullet point is on its own line.
        
        Returns:
            List of paragraphs, where each paragraph is a list of text strings
            and a list of separators between paragraphs
        """
        if not texts or not rec_boxes or len(texts) != len(rec_boxes):
            return [texts] if texts else [], []
        
        # Detect paragraph breaks and gap types
        separators = self.detect_paragraph_breaks(rec_boxes, texts)
        
        # Group into paragraphs
        paragraphs = []
        current_paragraph = []
        
        for i, (text, sep) in enumerate(zip(texts, separators)):
            if i == 0:
                # First block always starts a paragraph
                current_paragraph.append(text)
            elif sep == 0:
                # Same paragraph, add with space
                current_paragraph.append(text)
            else:
                # New paragraph (sep=1 or 2)
                if current_paragraph:
                    paragraphs.append((current_paragraph, separators[i]))
                current_paragraph = [text]
        
        # Add the last paragraph
        if current_paragraph:
            paragraphs.append((current_paragraph, 1))  # Default separator for last paragraph
        
        return paragraphs

    def format_text_with_paragraphs(self, texts, rec_boxes):
        """
        Format text with proper paragraph detection.
        Joins text within same paragraph with spaces, and paragraphs with newlines.
        Special handling for lists to ensure proper formatting.
        Extra newlines added when gap >= current block height.
        """
        if not texts:
            return ""
        
        # If no boxes available, fall back to simple newline joining
        if not rec_boxes or len(texts) != len(rec_boxes):
            # Still apply list detection even without boxes
            formatted_lines = []
            for text in texts:
                if self.is_bullet_point(text):
                    formatted_lines.append(text)
                else:
                    if formatted_lines and not self.is_bullet_point(formatted_lines[-1]):
                        formatted_lines[-1] += " " + text
                    else:
                        formatted_lines.append(text)
            return "\n".join(formatted_lines)
        
        # Group texts into paragraphs with separators
        paragraphs_with_seps = self.group_into_paragraphs(texts, rec_boxes)
        
        # Join within paragraphs with spaces, between paragraphs with appropriate newlines
        formatted_lines = []
        
        for para_idx, (paragraph, separator) in enumerate(paragraphs_with_seps):
            # Check if this paragraph is a list of bullet points
            if len(paragraph) > 1 and all(self.is_bullet_point(item) for item in paragraph):
                # This is a list - join with newlines instead of spaces
                for bullet_item in paragraph:
                    formatted_lines.append(bullet_item)
            elif len(paragraph) == 1 and self.is_bullet_point(paragraph[0]):
                # Single bullet point - add as its own line
                formatted_lines.append(paragraph[0])
            else:
                # Normal paragraph - join with spaces
                paragraph_text = " ".join(paragraph)
                formatted_lines.append(paragraph_text)
            
            # Add separator between paragraphs (except after the last one)
            if para_idx < len(paragraphs_with_seps) - 1:
                if separator == 2:
                    formatted_lines.append("")  # Double newline
                # separator == 1 gets a single newline (default when joining with \n)
        
        # Join paragraphs with newlines
        return "\n".join(formatted_lines)

    # ---------------------------------------------------------------------------
    #  Handle detection and output formatting
    # ---------------------------------------------------------------------------

    def has_twitter_timestamp(self, text):
        """
        Check if text contains a Twitter-style timestamp.
        Detects patterns like '· 23h', '· 1d', '· 3w', '· Jan 3', '· 14:30'.
        """
        if not text or not text.strip():
            return False

        timestamp_pattern = re.compile(
            r"·\s+"
            r"(?:"
            r"\d+[hmdw]"
            r"|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
            r"|"
            r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?"
            r"|"
            r"(?:Just now|Yesterday|Today|\d+\s+(?:min|hour|day|week|month|year)s?\s+ago)"
            r")"
            r"\s*"
            r"(?:[×Xx]|Follow(?:ing)?|Repost(?:ed)?|Like(?:d)?|Reply(?:ing)?|"
            r"\d+(?:\.\d+)?[KkMm]?|@\w+)?"
            r"\s*$",
            re.IGNORECASE,
        )

        return bool(timestamp_pattern.search(text.strip()))

    def is_statistics_line(self, text):
        """
        Detect lines that contain only statistics, engagement metrics, view counts,
        dates, or other non-content metadata (superfluous text).

        Detects patterns like:
        - '42 Retweets 4 Quotes 1,567 Likes'
        - '90.3K Views' / '61.8K' / '3.3M' / '80.4K'
        - 'Q281 t16,679' / 'D3 172 1,379 ill 80.4K'
        - '8:44 · 04 Dec 23 · 90.3K Views'
        - '04 Dec 23' (date-only lines)
        - '1.2M' / '16,679' / 't16,679' (pure number/abbreviation lines)
        """
        if not text or not text.strip():
            return False

        stripped = text.strip()

        # Pattern 1: Engagement keywords with numbers
        # e.g. "42 Retweets 4 Quotes 1,567 Likes"
        # e.g. "90.3K Views" / "1.2M Views"
        engagement_keywords = [
            r'Retweets?', r'Quotes?', r'Likes?', r'Views?', r'Reposts?',
            r'Replies?', r'Comments?', r'Shares?', r'Saves?', r'Bookmarks?',
            r'Impressions?', r'Engagements?', r'Followers?', r'Following?',
            r'Subscribers?', r'Liked', r'Reposted', r'Follow(?:ing)?',
        ]
        # Build a pattern that matches a line consisting mostly of numbers + these keywords
        # Allow: numbers (with K/M/B suffixes), commas, dots, the keywords, and some noise chars
        engagement_pattern = (
            r'^'
            r'[0-9,.\sKkMmBbTt' + ''.join(chr(c) for c in range(0x00A0, 0x00C0))  # include some unicode spaces
            + r']*'
            r'(?:' + '|'.join(engagement_keywords) + r')'
            r'[0-9,.\sKkMmBbTt]*'
            r'(?:' + '|'.join(engagement_keywords) + r')?'
            r'[0-9,.\sKkMmBbTt]*'
            r'(?:' + '|'.join(engagement_keywords) + r')?'
            r'[0-9,.\sKkMmBbTt]*'
            r'$'
        )
        if re.match(engagement_pattern, stripped, re.IGNORECASE):
            return True

        # Pattern 2: Date format "04 Dec 23" or "Dec 04, 2023" as the entire line
        date_pattern = re.compile(
            r'^'
            r'(?:'
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4}'
            r'|'
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{2,4}'
            r')'
            r'\s*$',
            re.IGNORECASE,
        )
        if date_pattern.match(stripped):
            return True

        # Pattern 3: Time + date + stats combo
        # e.g. "8:44 · 04 Dec 23 · 90.3K Views"
        time_date_stats_pattern = re.compile(
            r'^'
            r'\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?'  # time
            r'\s*[·\-–]\s*'  # separator
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4}'  # date
            r'(?:\s*[·\-–]\s*.+)?'  # optional more stuff after
            r'\s*$',
            re.IGNORECASE,
        )
        if time_date_stats_pattern.match(stripped):
            return True

        # Pattern 4: Lines that are mostly numbers/abbreviations with no real words
        # e.g. "Q281 t16,679" "61.8K ill 3.3M 8" "D3 172 1,379 ill 80.4K"
        # These consist of: optional letter prefix + numbers, commas, dots, K/M/B suffixes,
        # and at most 1-2 short "noise" words (like "ill", "t", "Q", "D")
        # Count "real words" (3+ alphabetic chars) vs non-word tokens
        tokens = stripped.split()
        real_word_count = 0
        stat_token_count = 0
        for token in tokens:
            # Check if it's a stat token: number-like (with K/M/B, commas, dots)
            if re.match(r'^[A-Za-z]?\d[\d,.]*[KkMmBbTt]?$', token):
                stat_token_count += 1
            # Check if it's a short noise word (1-2 chars, all alpha)
            elif re.match(r'^[A-Za-z]{1,2}$', token):
                stat_token_count += 1
            # Check if it's a pure number with commas
            elif re.match(r'^[\d,]+$', token):
                stat_token_count += 1
            # Check if it's a number+K/M suffix
            elif re.match(r'^\d+(?:\.\d+)?[KkMmBbTt]$', token):
                stat_token_count += 1
            # Otherwise it's a real word
            else:
                real_word_count += 1

        # If line has at least 2 tokens and >80% are stat tokens, it's a stat line
        if len(tokens) >= 2 and stat_token_count > 0 and real_word_count == 0:
            return True
        # Also catch lines with 1 real word and rest stats (e.g. "61.8K ill 3.3M 8")
        if len(tokens) >= 3 and stat_token_count >= 2 and real_word_count <= 1:
            return True

        # Pattern 5: Single token that is just a number/abbreviation (e.g. "16,679", "61.8K")
        # Only flag if it looks like a stat and is on its own line
        if len(tokens) == 1:
            single = tokens[0]
            # Pure number with optional commas
            if re.match(r'^[\d,]+$', single) and len(single) >= 3:
                return True
            # Number with K/M/B suffix
            if re.match(r'^\d+(?:\.\d+)?[KkMmBbTt]$', single):
                return True
            # Letter + number combo like "Q281", "D3", "t16,679"
            if re.match(r'^[A-Za-z]\d[\d,]*[KkMmBbTt]?$', single):
                return True

        return False

    def strip_statistics(self, text):
        """Remove lines that contain only statistics/engagement/date metadata."""
        if not text:
            return text
        lines = text.split("\n")
        cleaned = [
            line
            for line in lines
            if not self.is_statistics_line(line.strip())
        ]
        return "\n".join(cleaned)

    def detect_handles(self, text):
        """
        Scan OCR text for Twitter handles (@username).
        Removes lines containing handles and strips the nickname text immediately
        before a handle (e.g. 'John Doe @johndoe'), since that text is usually the
        poster's display name.

        Also handles the case where OCR splits nickname and handle across two lines:
            John Doe
            @johndoe
        -> both the nickname line and the @handle line are removed.

        Returns: (handles_list, cleaned_text)
        """
        if not text:
            return [], text

        lines = text.split("\n")
        handles = []
        cleaned_lines = []
        skip_next = False  # flag to skip a line that is a nickname for the next @handle line

        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue

            stripped = line.strip()

            # Case 1: nickname and handle on the same line, e.g. "John Doe @johndoe"
            match = re.match(r"^(.{0,20}?)@([\w.]+)$", stripped)
            if match:
                handle = "@" + match.group(2)
                handles.append(handle)
                # Remove the entire line (nickname + handle) from the body
                continue

            # Case 2: this line is just a @handle by itself
            handle_match = re.match(r"^@([\w.]+)$", stripped)
            if handle_match:
                handle = "@" + handle_match.group(1)
                handles.append(handle)
                # Remove the handle line from the body
                continue

            # Case 3: this line might be a nickname, and the next line is @handle
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                next_handle = re.match(r"^@([\w.]+)$", next_stripped)
                if next_handle:
                    # Current line is a nickname, next line is the handle
                    handle = "@" + next_handle.group(1)
                    handles.append(handle)
                    # Skip both the nickname line and the handle line
                    skip_next = True
                    continue

            # Not a handle-related line, keep as-is
            cleaned_lines.append(line)

        return handles, "\n".join(cleaned_lines)

    def strip_timestamps(self, text):
        """Remove lines that contain Twitter-style timestamps."""
        if not text:
            return text
        lines = text.split("\n")
        cleaned = [
            line
            for line in lines
            if not self.has_twitter_timestamp(line.strip())
        ]
        return "\n".join(cleaned)

    def split_into_tweet_chunks(self, text, max_chars=280):
        """
        Split text into chunks of max_chars, breaking at sentence boundaries
        (period, newline, etc.) when possible.
        """
        if not text:
            return []

        chunks = []
        paragraphs = text.split("\n\n")

        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chars:
                final_chunks.append(chunk)
            else:
                sentences = re.split(r"(?<=[.!?])\s+", chunk)
                temp = ""
                for sent in sentences:
                    if len(temp) + len(sent) + 1 > max_chars and temp:
                        final_chunks.append(temp.strip())
                        temp = sent
                    else:
                        if temp:
                            temp += " " + sent
                        else:
                            temp = sent
                if temp:
                    final_chunks.append(temp.strip())

        return final_chunks

    def format_as_tweet(self, text):
        """
        Format as: 'tweet by @handle that says [body]'
        Strips timestamps, statistics, and handle lines from the body.
        """
        if not text:
            return text

        cleaned = self.strip_timestamps(text)
        cleaned = self.strip_statistics(cleaned)
        handles, cleaned = self.detect_handles(cleaned)
        cleaned = cleaned.strip()

        handle_str = handles[0] if handles else "@unknown"
        return f"tweet by {handle_str} that says \n{cleaned}"

    def format_as_tweet_thread(self, text):
        """
        Format as:
        tweet thread that goes as follows

        @handle1:
        > [chunk1]

        @handle2:
        > [chunk2]
        ...
        """
        if not text:
            return text

        cleaned = self.strip_timestamps(text)
        cleaned = self.strip_statistics(cleaned)
        handles, cleaned = self.detect_handles(cleaned)
        cleaned = cleaned.strip()

        chunks = self.split_into_tweet_chunks(cleaned, 280)

        if not chunks:
            return text

        lines = ["tweet thread that goes as follows", ""]
        for i, chunk in enumerate(chunks):
            handle = handles[i] if i < len(handles) else (
                handles[-1] if handles else "@unknown"
            )
            lines.append(f"{handle}:")
            lines.append(f"> {chunk}")
            if i < len(chunks) - 1:
                lines.append("")

        return "\n".join(lines)

    def format_as_quote_retweet(self, text):
        """
        Format as:
        quote retweet. the original tweet is by @handle_a and says
        > [original_text]. @handle_b then quote retweets this and says
        > [comment_text]
        """
        if not text:
            return text

        cleaned = self.strip_timestamps(text)
        cleaned = self.strip_statistics(cleaned)
        handles, cleaned = self.detect_handles(cleaned)
        cleaned = cleaned.strip()

        parts = re.split(r"\n\n+", cleaned, maxsplit=1)

        if len(parts) >= 2:
            original_text = parts[0].strip()
            comment_text = parts[1].strip()
        else:
            mid = len(cleaned) // 2
            split_pos = cleaned.rfind("\n\n", 0, mid)
            if split_pos == -1:
                split_pos = cleaned.rfind(". ", 0, mid)
                if split_pos != -1:
                    split_pos += 1
                else:
                    split_pos = mid
            original_text = cleaned[:split_pos].strip()
            comment_text = cleaned[split_pos:].strip()

        handle_a = handles[0] if len(handles) > 0 else "@original"
        handle_b = handles[1] if len(handles) > 1 else (
            handles[0] if handles else "@commenter"
        )

        return (
            f"quote retweet. the original tweet is by {handle_a} and says\n"
            f"> {original_text}. \n{handle_b} then quote retweets this and says\n"
            f"> {comment_text}"
        )

    def format_as_reddit_post(self, text):
        """WIP: Return raw OCR text unchanged."""
        return text

    def format_as_reddit_comment(self, text):
        """WIP: Return raw OCR text unchanged."""
        return text

    def format_as_reddit_thread(self, text):
        """WIP: Return raw OCR text unchanged."""
        return text

    def paste_from_clipboard(self, event=None):
        """Handle image paste from clipboard"""
        try:
            # Get image from clipboard (requires PIL)
            clipboard_image = ImageGrab.grabclipboard()
            
            if clipboard_image is None:
                self.status_var.set("No image found in clipboard. Copy an image first (Print Screen or Ctrl+C on an image)")
                return
                
            if isinstance(clipboard_image, Image.Image):
                self.current_image = clipboard_image
                self.annotated_image = None
                self.display_image(self.current_image)
                self.status_var.set("Image pasted successfully! Click 'Process Image' to extract text")
                self.process_button.config(state='normal')
                self.clear_button.config(state='normal')
                if self.auto_process_var.get():
                    self.root.after(100, self.process_image)
            else:
                self.status_var.set("Clipboard does not contain an image. Please copy an image first.")
                
        except Exception as e:
            self.status_var.set(f"Error pasting image: {str(e)}")
            messagebox.showerror("Error", f"Failed to paste image: {str(e)}")
    
    def display_image(self, image):
        """Display the image in the GUI with proper scaling"""
        # Get the image frame dimensions
        self.image_frame.update_idletasks()
        max_width = self.image_frame.winfo_width() - 20
        max_height = 400
        
        if max_width <= 0:
            max_width = 400
            
        # Calculate scaling factor
        img_width, img_height = image.size
        scale = min(max_width / img_width, max_height / img_height, 1.0)
        new_size = (int(img_width * scale), int(img_height * scale))
        
        # Resize and display
        resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized_image)
        
        self.image_label.config(image=photo)
        self.image_label.image = photo  # Keep a reference
        
    def process_image(self):
        """Process the image with PaddleOCR to extract text"""
        if self.current_image is None or self.ocr_model is None:
            return
            
        try:
            self.status_var.set("Processing image with PaddleOCR...")
            self.root.update()
            
            # Resize large images to prevent memory exhaustion during OCR.
            # Very tall images (e.g. Twitter thread screenshots) can cause
            # PaddleOCR to detect hundreds of text blocks, each requiring a
            # separate recognition inference — which can exhaust system memory.
            # We limit the max dimension to 1280px while preserving aspect ratio.
            img = self.current_image
            max_dim = 1280
            scale_x = 1.0
            scale_y = 1.0
            if max(img.size) > max_dim:
                scale = max_dim / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                scale_x = self.current_image.width / new_size[0]
                scale_y = self.current_image.height / new_size[1]
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                self.status_var.set(f"Resized image from {self.current_image.size} to {new_size} for OCR...")
                self.root.update()
            
            # Convert PIL Image to format PaddleOCR expects
            # Save to bytes, then read - simpler approach
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name
                img.save(temp_path, 'PNG')
            
            # Perform OCR using PaddleOCR.
            # Force the text detection model to internally resize images so the
            # longest side is at most 960px (limit_type="max"). The default config
            # uses limit_type="min" with limit_side_len=64, which acts as a minimum
            # size floor — it does NOT downscale large images. Without this, dense
            # screenshots like Twitter threads produce many text blocks that exhaust
            # memory during text recognition.
            result = self.ocr_model.predict(
                temp_path,
                text_det_limit_side_len=960,
                text_det_limit_type="max",
            )
        
            # Clean up temp file
            os.unlink(temp_path)
            
            if result and len(result) > 0 and result[0] is not None:
                # Extract text from PaddleOCR result structure
                min_confidence = self.confidence_var.get()
                extracted_lines = []
                confidence_info = []
                rec_boxes = []  # Store bounding boxes for paragraph detection
                
                annotated_image = self.current_image.copy()
                draw = ImageDraw.Draw(annotated_image)
                
                # Helper to scale polygon coordinates from OCR-resized space back
                # to original image space, so red boxes are drawn correctly.
                def scale_poly(poly):
                    return [(int(p[0] * scale_x), int(p[1] * scale_y)) for p in poly]
                
                # result[0] contains the detection results for the first image
                # Access .json once to avoid triggering _to_json() multiple times
                # (hasattr calls the property getter, so each access is expensive)
                result_json = result[0].json if hasattr(result[0], 'json') else None
                if result_json is not None and isinstance(result_json, dict) and 'res' in result_json:
                    res = result_json['res']
                    texts = res.get('rec_texts', [])
                    scores = res.get('rec_scores', [])
                    polys = res.get('dt_polys', []) or res.get('rec_polys', [])
                    
                    for i, (text, confidence) in enumerate(zip(texts, scores)):
                        if confidence >= min_confidence:
                            extracted_lines.append(text)
                            confidence_info.append(f"{confidence:.2f}")
                            if i < len(polys):
                                poly = polys[i]
                                # Scale polygon coordinates to original image space
                                scaled_poly = scale_poly(poly)
                                # Convert polygon to bounding box [x1, y1, x2, y2]
                                all_x = [p[0] for p in scaled_poly]
                                all_y = [p[1] for p in scaled_poly]
                                bbox = [min(all_x), min(all_y), max(all_x), max(all_y)]
                                rec_boxes.append(bbox)
                                points = [(p[0], p[1]) for p in scaled_poly]
                                if points:
                                    points.append(points[0])
                                    draw.line(points, fill="red", width=2)
                elif isinstance(result[0], dict) and 'res' in result[0]:
                    res = result[0]['res']
                    texts = res.get('rec_texts', [])
                    scores = res.get('rec_scores', [])
                    polys = res.get('dt_polys', []) or res.get('rec_polys', [])
                    
                    for i, (text, confidence) in enumerate(zip(texts, scores)):
                        if confidence >= min_confidence:
                            extracted_lines.append(text)
                            confidence_info.append(f"{confidence:.2f}")
                            if i < len(polys):
                                poly = polys[i]
                                # Scale polygon coordinates to original image space
                                scaled_poly = scale_poly(poly)
                                # Convert polygon to bounding box [x1, y1, x2, y2]
                                all_x = [p[0] for p in scaled_poly]
                                all_y = [p[1] for p in scaled_poly]
                                bbox = [min(all_x), min(all_y), max(all_x), max(all_y)]
                                rec_boxes.append(bbox)
                                points = [(p[0], p[1]) for p in scaled_poly]
                                if points:
                                    points.append(points[0])
                                    draw.line(points, fill="red", width=2)
                else:
                    for line in result[0]:
                        poly = line[0]
                        text = line[1][0]  # The recognized text
                        confidence = line[1][1]  # Confidence score (0-1)
                        
                        if confidence >= min_confidence:
                            extracted_lines.append(text)
                            confidence_info.append(f"{confidence:.2f}")
                            # Scale polygon coordinates to original image space
                            scaled_poly = scale_poly(poly)
                            # Convert polygon to bounding box
                            all_x = [p[0] for p in scaled_poly]
                            all_y = [p[1] for p in scaled_poly]
                            bbox = [min(all_x), min(all_y), max(all_x), max(all_y)]
                            rec_boxes.append(bbox)
                            points = [(p[0], p[1]) for p in scaled_poly]
                            if points:
                                points.append(points[0])
                                draw.line(points, fill="red", width=2)
                
                if extracted_lines:
                    # Use paragraph-aware formatting with bounding boxes
                    raw_text = self.format_text_with_paragraphs(extracted_lines, rec_boxes)
                    
                    # Save the original full OCR text for dynamic reformatting
                    self.raw_ocr_text = raw_text
                    
                    # Apply selected output formatting
                    output_type = self.output_type_var.get()
                    formatter = {
                        "tweet": self.format_as_tweet,
                        "tweet thread": self.format_as_tweet_thread,
                        "quote retweet": self.format_as_quote_retweet,
                        "reddit post": self.format_as_reddit_post,
                        "reddit comment": self.format_as_reddit_comment,
                        "reddit thread": self.format_as_reddit_thread,
                    }
                    formatter_func = formatter.get(output_type, self.format_as_tweet)
                    full_text = formatter_func(raw_text)
                    
                    # Clear text widget and insert formatted text
                    self.text_widget.delete(1.0, tk.END)
                    self.text_widget.insert(1.0, full_text)
                    
                    self.annotated_image = annotated_image
                    self.display_image(self.annotated_image)
                    
                    # Optionally show confidence info in status
                    avg_conf = sum(float(c) for c in confidence_info) / len(confidence_info) if confidence_info else 0
                    self.status_var.set(f"OCR complete! Extracted {len(extracted_lines)} text blocks. Avg confidence: {avg_conf:.2f}")
                    self.copy_button.config(state='normal')
                else:
                    self.text_widget.delete(1.0, tk.END)
                    self.text_widget.insert(1.0, f"No text detected above confidence threshold ({min_confidence}).\n\nTry:\n• Lowering the confidence threshold\n• Using a clearer image\n• Selecting a different language")
                    self.status_var.set("No text detected above confidence threshold")
            else:
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(1.0, "No text detected in the image.\n\nTry:\n• Using a clearer image\n• Selecting a different language")
                self.status_var.set("No text detected in the image")
                
        except Exception as e:
            self.status_var.set(f"OCR Error: {str(e)}")
            messagebox.showerror("OCR Error", f"Failed to process image: {str(e)}")
    
    def on_output_type_change(self, event=None):
        """Re-format the displayed text when the output type dropdown changes."""
        if self.raw_ocr_text is None:
            return  # No OCR results yet

        output_type = self.output_type_var.get()
        formatter = {
            "tweet": self.format_as_tweet,
            "tweet thread": self.format_as_tweet_thread,
            "quote retweet": self.format_as_quote_retweet,
            "reddit post": self.format_as_reddit_post,
            "reddit comment": self.format_as_reddit_comment,
            "reddit thread": self.format_as_reddit_thread,
        }
        formatter_func = formatter.get(output_type, self.format_as_tweet)
        full_text = formatter_func(self.raw_ocr_text)

        # Update the text widget with the newly formatted text
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, full_text)
        self.status_var.set(f"Reformatted as {output_type}")

    def copy_to_clipboard(self):
        """Copy extracted text to clipboard with output formatting"""
        text = self.text_widget.get(1.0, tk.END).strip()
        if text:
            output_type = self.output_type_var.get()
            formatter = {
                "tweet": self.format_as_tweet,
                "tweet thread": self.format_as_tweet_thread,
                "quote retweet": self.format_as_quote_retweet,
                "reddit post": self.format_as_reddit_post,
                "reddit comment": self.format_as_reddit_comment,
                "reddit thread": self.format_as_reddit_thread,
            }
            formatter_func = formatter.get(output_type, self.format_as_tweet)
            # Use raw_ocr_text if available, otherwise fall back to widget text
            source_text = self.raw_ocr_text if self.raw_ocr_text else text
            formatted_text = formatter_func(source_text)
            pyperclip.copy(formatted_text)
            self.status_var.set(
                f"Copied {len(formatted_text)} characters as {output_type}!"
            )

            # Flash the copy button to provide visual feedback
            self.copy_button.config(text="✓ Copied!")
            self.root.after(2000, lambda: self.copy_button.config(text="📋 Copy to Clipboard"))
    
    def clear_all(self):
        """Clear the image and text"""
        self.current_image = None
        self.annotated_image = None
        self.current_ocr_result = None
        self.raw_ocr_text = None
        self.image_label.config(image='', text="No image pasted yet\n\nPress Ctrl+V to paste an image")
        self.image_label.image = None
        self.text_widget.delete(1.0, tk.END)
        self.copy_button.config(state='disabled')
        self.process_button.config(state='disabled')
        self.status_var.set("Cleared - Press Ctrl+V to paste a new image")


def main():
    root = TkinterDnD.Tk()
    app = PaddleOCRApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()