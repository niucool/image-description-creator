from paddleocr import PaddleOCR
import numpy as np
import json

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

lang_code='en'
ocr_model = PaddleOCR(
	use_doc_orientation_classify=False,
	use_doc_unwarping=False,
	use_textline_orientation=False,
	enable_mkldnn=False,
	lang=lang_code)

img_file = r'c:\Projects\github\image-description-creator\twitter_thread.png'
result = ocr_model.predict(img_file)
with open("data.json", "w", encoding="utf-8") as f:
    # json.dump(str(result), f, cls=NumpyEncoder, indent=4)
    f.write(str(result))