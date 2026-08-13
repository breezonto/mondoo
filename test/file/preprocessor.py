from mondoo.mdo.io.file.pdf import convert_pdf_to_images


if __name__ == '__main__':
    convert_pdf_to_images(pdf_path="/home/guard/resource/Dungeons Dragons Monster Manual.pdf", out_path="/home/guard/resource/monster-manual")

    # body = extarct_pdf_body('/home/guard/file/中国能源金融发展报告+（2025+年）.pdf',)
    
    # dump_pdf_body_to_md(
    #     body,
    #     md_out_path = '/home/guard/cache/test/中国能源金融发展报告+（2025+年）/paragraphs.md',
    #     image_dir   = '/home/guard/cache/test/中国能源金融发展报告+（2025+年）/images',
    #     vector_dir  = '/home/guard/cache/test/中国能源金融发展报告+（2025+年）/vectors'
    # )