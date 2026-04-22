import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import pytesseract
import pyperclip
import io
import sys

# Configure Tesseract path (update this to your installation path)
# Windows example - adjust the path to match your installation
if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r'E:\Tesseract-OCR\tesseract.exe'
# On macOS, it's usually in PATH automatically after `brew install tesseract`
# On Linux, it's typically in PATH after `sudo apt install tesseract-ocr`

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Image to Text Tool")
        self.root.geometry("900x700")
        
        # Store the current image
        self.current_image = None
        
        self.setup_ui()
        self.setup_bindings()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions label
        instruction_text = "📋 Press Ctrl+V to paste an image from clipboard\n"
        instruction_text += "🖼️ Supported formats: PNG, JPEG, BMP, GIF"
        instructions = ttk.Label(main_frame, text=instruction_text, 
                                  font=('Arial', 10), foreground='gray')
        instructions.pack(pady=5)
        
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
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Press Ctrl+V to paste an image")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))
        
    def setup_bindings(self):
        # Bind Ctrl+V to paste from clipboard
        self.root.bind('<Control-v>', self.paste_from_clipboard)
        
    def paste_from_clipboard(self, event=None):
        """Handle image paste from clipboard"""
        try:
            # Get image from clipboard
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
        """Process the image with OCR to extract text"""
        if self.current_image is None:
            return
            
        try:
            self.status_var.set("Processing image with OCR...")
            self.root.update()
            
            # Optional: Add image preprocessing for better accuracy
            processed_image = self.preprocess_image(self.current_image)
            
            # Perform OCR
            # Use English by default, add 'chi_sim' for Chinese, 'spa' for Spanish, etc.
            extracted_text = pytesseract.image_to_string(processed_image, lang='eng')
            
            if extracted_text.strip():
                # Clear text widget and insert extracted text
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(1.0, extracted_text)
                self.copy_button.config(state='normal')
                self.status_var.set(f"OCR complete! Extracted {len(extracted_text.split())} words")
            else:
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(1.0, "No text detected in the image.\n\nTry:\n• Using a clearer image\n• Adjusting the image contrast\n• Installing additional language packs for Tesseract")
                self.status_var.set("No text detected in the image")
                
        except pytesseract.TesseractNotFoundError:
            messagebox.showerror("Tesseract Error", 
                               "Tesseract is not installed or not found in PATH.\n\n"
                               "Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
                               "Mac: brew install tesseract\n"
                               "Linux: sudo apt install tesseract-ocr")
            self.status_var.set("Tesseract not found - please install it first")
        except Exception as e:
            self.status_var.set(f"OCR Error: {str(e)}")
            messagebox.showerror("OCR Error", f"Failed to process image: {str(e)}")
    
    def preprocess_image(self, image):
        """Optional: Preprocess image for better OCR accuracy"""
        # Convert to grayscale for better contrast
        if image.mode != 'L':
            image = image.convert('L')
        return image
    
    def copy_to_clipboard(self):
        """Copy extracted text to clipboard"""
        text = self.text_widget.get(1.0, tk.END).strip()
        if text:
            pyperclip.copy(text)
            self.status_var.set(f"Copied {len(text)} characters to clipboard!")
            
            # Optional: Flash the copy button to provide visual feedback
            self.copy_button.config(text="✓ Copied!")
            self.root.after(2000, lambda: self.copy_button.config(text="📋 Copy to Clipboard"))
    
    def clear_all(self):
        """Clear the image and text"""
        self.current_image = None
        self.image_label.config(image='', text="No image pasted yet\n\nPress Ctrl+V to paste an image")
        self.image_label.image = None
        self.text_widget.delete(1.0, tk.END)
        self.copy_button.config(state='disabled')
        self.process_button.config(state='disabled')
        self.status_var.set("Cleared - Press Ctrl+V to paste a new image")


# Note: You need to import ImageGrab properly
from PIL import ImageGrab

def main():
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()