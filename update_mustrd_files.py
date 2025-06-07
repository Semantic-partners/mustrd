import os
import re

def update_mustrd_files(directory, infix_to_strip):
    """
    Updates mustrd.ttl files in the specified directory and its subdirectories by replacing
    must:file "string" with must:fileurl <file://./string>, rewriting paths starting with the specified infix.

    Args:
        directory (str): Path to the directory containing mustrd.ttl files.
        infix_to_strip (str): Infix to strip from file paths.
    """
    ttl_files = []
    for root, _, files in os.walk(directory):
        ttl_files.extend(os.path.join(root, f) for f in files if f.endswith('.mustrd.ttl'))

    for ttl_file in ttl_files:
        with open(ttl_file, 'r') as file:
            content = file.read()

        # Replace must:file "string" with must:fileurl <file://./string>, rewriting paths
        # Why: The infix handling is necessary to adapt file paths for compatibility
        # with runtime environments and tools that expect standardized or relative paths.
        updated_content = re.sub(fr'must:file\s+"([^"]*{infix_to_strip}/)([^"]+)"', r'must:fileurl <file://./\1\2>', content)

        with open(ttl_file, 'w') as file:
            file.write(updated_content)

        print(f"Updated {ttl_file}")

if __name__ == "__main__":
    directory = input("Enter the directory containing mustrd.ttl files: ")
    infix_to_strip = input("Enter the infix to strip from file paths: ")
    update_mustrd_files(directory, infix_to_strip)
