import os
import re

def update_mustrd_files(directory):
    """
    Updates mustrd.ttl files in the specified directory and its subdirectories by replacing
    must:file "string" with must:fileurl <file://./string>, rewriting paths starting with '../../test/data' to './../../data'.

    Args:
        directory (str): Path to the directory containing mustrd.ttl files.
    """
    ttl_files = []
    for root, _, files in os.walk(directory):
        ttl_files.extend(os.path.join(root, f) for f in files if f.endswith('.mustrd.ttl'))

    for ttl_file in ttl_files:
        with open(ttl_file, 'r') as file:
            content = file.read()

        # Replace must:file "string" with must:fileurl <file://./string>, rewriting paths
        
        updated_content = re.sub(r'must:file\s+"../../test/data/([^\"]+)"', r'must:fileurl <file://./../../data/\1>', content)

        with open(ttl_file, 'w') as file:
            file.write(updated_content)

        print(f"Updated {ttl_file}")

if __name__ == "__main__":
    directory = input("Enter the directory containing mustrd.ttl files: ")
    update_mustrd_files(directory)
