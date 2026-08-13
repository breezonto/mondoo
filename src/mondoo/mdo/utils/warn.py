
def WarnNotImplemented(
    func_name : str,
    cls_name  : str = None
):
    if cls_name is not None:
        print(f"{func_name} of current class {cls_name} isn't implemented!") 
    else:
        print(f"The text method of current class {cls_name} isn't implemented!")
    
    return None