import os
import patoolib
import asyncio

async def extract_3d_files(file_path: str, extract_dir: str) -> list[str]:
    """
    Extract an archive and return paths to all .stl and .obj files inside.
    If the file is already a .stl/.obj, it just returns a list with that file.
    """
    file_ext = file_path.split('.')[-1].lower()
    
    if file_ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene']:
        return [file_path]
        
    os.makedirs(extract_dir, exist_ok=True)
    
    # Run patoolib extraction in a thread to avoid blocking asyncio
    await asyncio.to_thread(patoolib.extract_archive, file_path, outdir=extract_dir, verbosity=-1)
    
    extracted_3d_files = []
    all_files_found = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            all_files_found.append(file)
            ext = file.split('.')[-1].lower()
            if ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene']:
                extracted_3d_files.append(os.path.join(root, file))
                
    if not extracted_3d_files:
        import logging
        logging.getLogger(__name__).warning(f"No 3D files found. Files in archive: {all_files_found}")
        
    return extracted_3d_files

async def download_telegram_document(client, message, save_dir: str) -> str:
    """
    Download a document from a telegram message to the given directory.
    Returns the path to the downloaded file.
    """
    os.makedirs(save_dir, exist_ok=True)
    return await client.download_media(message.document, file=save_dir)
