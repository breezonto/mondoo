from mondoo.mdo.utils.decorator.banner import with_duration_banner
from mondoo.mdo.engine.manager.file_descriptor          import FDManager


if __name__ == '__main__':
    @with_duration_banner("Test available methods")
    def test_avail_methods():
        methods = FDManager.get_available_methods('pdf')
        print(f"Available methods of pdf: {methods}")
        
        methods = FDManager.get_available_methods('docx')
        print(f"Available methods of docx: {methods}")
        
        methods = FDManager.get_available_methods('png')
        print(f"Available methods of png: {methods}")
        
        methods = FDManager.get_available_methods('jpg')
        print(f"Available methods of jpg: {methods}")
    
    @with_duration_banner("Test FileManager.open()")
    def test_open():    
        objs = FDManager.open(
            path           = '/home/guard/file/威海市重大突发事件应急保障体系建设规划.pdf',
            meth_names     = ['text'],
            file_id        = '000000'
        )
        
        objs = FDManager.open(
            path           = '/home/guard/file/中国能源金融发展报告+（2025+年）.pdf',
            meth_names     = ['text'],
            file_id        = '111111'
        )
        
        for obj in objs:
            FDManager.dump(obj)
            FDManager.export(obj)
            
    units = [
        test_avail_methods,
        # test_open
    ]
    
    for unit in units:
        unit()