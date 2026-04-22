import pytesseract
from PIL import Image
import re
import sys


pytesseract.pytesseract.tesseract_cmd = r'E:\Tesseract-OCR\tesseract.exe'

def classify_screenshot_by_text(image_path):
    """Extract text with OCR, then classify by keyword patterns"""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img).lower()
    
    # Twitter/X patterns - the text you described
    twitter_patterns = {
        'retweet': r'retweet',
        'reply': r'repl(y|ies)', 
        'like': r'like',
        'engagement': r'[\d,]+ retweets?[\s,]+[\d,]+ likes?'
    }
    
    # Reddit patterns
    reddit_patterns = {
        'reply': r'reply',
        'award': r'award',
        'share': r'share',
        'engagement': r'[\d,]+ points?[\s·]+[\d,]+ comments?'
    }
    
    # Check for matches
    if any(re.search(pattern, text) for pattern in ['retweet', 'like']):
        return 'twitter_post'
    
    if re.search(r'reply.*award.*share', text, re.DOTALL) or re.search(r'save.*report.*reply', text, re.DOTALL):
        return 'reddit_comment'
    
    return 'unknown'

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_with_your_images.py <screenshot_path>")
        print("Example: python test_with_your_images.py my_tweet.png")
        return
    
    image_path = sys.argv[1]
    
    print(classify_screenshot_by_text(image_path))
    

if __name__ == "__main__":
    main()