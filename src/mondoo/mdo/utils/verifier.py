import hashlib
import os
from typing import BinaryIO, Literal

def sha256(file_obj: BinaryIO) -> str:
    """Compute SHA-256 hash of a file-like object"""
    hash_obj = hashlib.sha256()
    file_obj.seek(0)  # make sure to start from beginning
    
    for chunk in iter(lambda: file_obj.read(8192), b""):
        hash_obj.update(chunk)
    
    file_obj.seek(0)  # reset pointer if you need to read the file again
    return hash_obj.hexdigest()


def md5(file_obj: BinaryIO) -> str:
    """Compute MD5 hash of a file"""
    hash_obj = hashlib.md5()
    file_obj.seek(0)  # make sure to start from beginning
    for chunk in iter(lambda: file_obj.read(8192), b""):
        hash_obj.update(chunk)
    
    file_obj.seek(0)  # reset pointer if you need to read the file again
    return hash_obj.hexdigest()


def sha256_from_path(path: str) -> str:
    """Compute SHA-256 hash of a file"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    
    with open(path, "rb") as f:
        hash_obj = sha256(f)
    
    return hash_obj.hexdigest()


def md5_from_path(path: str) -> str:
    """Compute MD5 hash of a file"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    
    with open(path, "rb") as f:
        hash_obj = md5(f)
    return hash_obj.hexdigest()


def checksum(
    file_object: BinaryIO,
    algorithm: Literal["sha256", "md5"] = "sha256"
) -> str:
    """Compute checksum of a file using specified algorithm"""
    if algorithm == "sha256":
        return sha256(file_object)
    
    if algorithm == "md5":
        return md5(file_object)
    
    raise ValueError("Unsupported algorithm. Use 'sha256' or 'md5'.")


def checksum_from_path(
    path: str, 
    algorithm: Literal["sha256", "md5"] = "sha256"
) -> str:
    
    """Compute checksum of a file using specified algorithm"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} does not exist")
    
    with open(path, "rb") as f:
        if algorithm == "sha256":
            return sha256(f)
        
        if algorithm == "md5":
            return md5(f)
        
        raise ValueError("Unsupported algorithm. Use 'sha256' or 'md5'.")
        

if __name__ == "__main__":
    # Compute hashes
    hash1 = sha256_from_path("file1.bin")
    hash2 = md5_from_path("file2.bin")

    # Compare
    if hash1 == hash2:
        print("Files are identical!")
    else:
        print("Files differ.")