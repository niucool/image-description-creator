import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import pyperclip
import io
import sys
from paddleocr import PaddleOCR
import numpy as np

class PaddleOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PaddleOCR Image to Text Tool")
        self.root.geometry("900x700")
        
        # Store the current image and OCR results
        self.current_image = None
        self.ocr_model = None
        self.current_ocr_result = None
        
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
        instruction_text = "📋 Press Ctrl+V to paste an image from clipboard\n"
        instruction_text += "🖼️ Supports: PNG, JPEG, BMP, GIF | Built-in PaddleOCR engine"
        instructions = ttk.Label(control_frame, text=instruction_text, foreground='gray')
        instructions.pack(side=tk.LEFT, padx=(10, 0))
        
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
        self.confidence_label.setText(f"{float(value):.2f}")
        
    def setup_bindings(self):
        # Bind Ctrl+V to paste from clipboard
        self.root.bind('<Control-v>', self.paste_from_clipboard)
        
    def init_ocr_model(self):
        """Initialize PaddleOCR model - runs once at startup"""
        try:
            self.status_var.set("Initializing PaddleOCR model (first time may take a moment)...")
            self.root.update()
            
            # Get selected language code
            lang_code = self.languages[self.lang_var.get()]
            
            # Initialize PaddleOCR[citation:5][citation:7]
            # use_angle_cls=True enables text direction classification for better accuracy
            self.ocr_model = PaddleOCR(use_angle_cls=True, lang=lang_code)
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
    
    def paste_from_clipboard(self, event=None):
        """Handle image paste from clipboard"""
        try:
            # Get image from clipboard (requires PIL)
            from PIL import ImageGrab
            clipboard_image = ImageGrab.grabclipboard()
            
            if clipboard_image is None:
                self.status_var.set("No image found in clipboard. Copy an image first (Print Screen or Ctrl+C on an image)")
                return
                
            if isinstance(clipboard_image, Image.Image):
                self.current_image = clipboard_image
                self.display_image(self.current_image)
                self.status_var.set("Image pasted successfully! Click 'Process Image' to extract text")
                self.process_button.config(state='normal')
                self.clear_button.config(state='normal')
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
            
            # Convert PIL Image to format PaddleOCR expects
            # Save to bytes, then read - simpler approach
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name
                self.current_image.save(temp_path, 'PNG')
            
            # Perform OCR using PaddleOCR[citation:3][citation:5]
            # Result format: list of lists containing [[coordinates], (text, confidence)]
            result = self.ocr_model.predict(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            if result and len(result) > 0 and result[0] is not None:
                # Extract text from PaddleOCR result structure
                min_confidence = self.confidence_var.get()
                extracted_lines = []
                confidence_info = []
                
                # result[0] contains the detection results for the first image
                for line in result[0]:
                    text = line[1][0]  # The recognized text
                    confidence = line[1][1]  # Confidence score (0-1)
                    
                    if confidence >= min_confidence:
                        extracted_lines.append(text)
                        confidence_info.append(f"{confidence:.2f}")
                
                if extracted_lines:
                    full_text = "\n".join(extracted_lines)
                    
                    # Clear text widget and insert extracted text
                    self.text_widget.delete(1.0, tk.END)
                    self.text_widget.insert(1.0, full_text)
                    
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
    
    def copy_to_clipboard(self):
        """Copy extracted text to clipboard"""
        text = self.text_widget.get(1.0, tk.END).strip()
        if text:
            pyperclip.copy(text)
            self.status_var.set(f"Copied {len(text)} characters to clipboard!")
            
            # Flash the copy button to provide visual feedback
            self.copy_button.config(text="✓ Copied!")
            self.root.after(2000, lambda: self.copy_button.config(text="📋 Copy to Clipboard"))
    
    def clear_all(self):
        """Clear the image and text"""
        self.current_image = None
        self.current_ocr_result = None
        self.image_label.config(image='', text="No image pasted yet\n\nPress Ctrl+V to paste an image")
        self.image_label.image = None
        self.text_widget.delete(1.0, tk.END)
        self.copy_button.config(state='disabled')
        self.process_button.config(state='disabled')
        self.status_var.set("Cleared - Press Ctrl+V to paste a new image")


def main():
    root = tk.Tk()
    app = PaddleOCRApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()