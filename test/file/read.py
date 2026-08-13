from mondoo.mdo.utils.decorator.banner import with_duration_banner
from mondoo.mdo.io.reader              import *


if __name__ == '__main__':
    @with_duration_banner("test PDFReader")
    def test_pdf_reader():
        object = PDFReader.read(
            path              = '/home/guard/file/中国能源金融发展报告+（2025+年）.pdf',
            meth_names        = 'text',
            # intermediate_path = '/home/guard/cache/intermediate/2024中国再生资源回收行业发展报告.json',
            # cover_pages       = [1],
            # category_pages    = [4]
        )
        
        PDFReader.dump(object.body, path='/home/guard/cache/test/中国能源金融发展报告+（2025+年）')
        print(f"The total word count: {object.body.total_words}")
    
    @with_duration_banner("Test DOCXReader")
    def test_docx_reader():
        object = PDFReader.read(
            path              = '/home/guard/file/中国能源金融发展报告+（2025+年）.pdf',
            meth_names        = 'text',
            # intermediate_path = '/home/guard/cache/intermediate/四川省再生资源回收循环利用行动方案.json'
        )
        
        print(f"The total word count: {object.body.total_words}")  
    
    @with_duration_banner("Test ImageReader")
    def test_picture_reader():
        object = ImageReader.read(
            path              = '/home/guard/file/2026-05-08.png',
            meth_names        = 'ocr',
            intermediate_path = '/home/guard/cache/intermediate/2026-05-08'
        )

        # ImageReader.dump(object.body, path='/home/guard/cache/test/2026-05-08')
        print(f"The total word count: {object.body.total_words}")
        
    units = [
        # test_pdf_reader,
        # test_docx_reader
        test_picture_reader
    ]
    
    for unit in units:
        unit()