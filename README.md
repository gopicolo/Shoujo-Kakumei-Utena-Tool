# Shoujo-Kakumei-Utena-Tool
A tool for extracting, editing, and reinserting text in Shoujo Kakumei Utena Itsuka Kakumeisareru Monogatari, (Sega Saturn). 
# SCN Script Dumping & Repacking Tools

These Python scripts are designed to **extract, clean, and reinsert translated text** from `.SCN` files from Shoujo Kakumei Utena Itsuka Kakumeisareru Monogatari

## Features

- **`dump.py`** – Extracts text from `.SCN` files, mapping pointers automatically and saving a structured dump.  
  - Detects valid text strings via pointer scanning.  
  - Outputs formatted text with tags for control codes.  
  - Filters out garbage or invalid strings (optional).  

- **`refine.py`** – Applies stricter filtering to previously dumped `.txt` files.  
  - Removes control-code-heavy fragments.  
  - Discards duplicates and substrings.  
  - Produces a clean, renumbered text file ready for translation.  

- **`repack.py`** – Rebuilds `.SCN` files using translated `.txt` files.  
  - Reinserts text without adding artificial terminators.  
  - Preserves original padding, null bytes, and orphaned data between strings.  
  - Automatically recalculates and rewrites all pointers.

## How It Works

1. **Dump phase (`dump.py`)**  
   - Place your `.SCN` files in the `input` folder.  
   - Run `python dump.py` to generate text dumps in `output/`.  
   - These files contain string offsets, pointer locations, and original control codes.  

2. **Refinement phase (`refine.py`)**  
   - Place the raw dump `.txt` files in the `output` folder.  
   - Run `python refine.py` to generate cleaned files in `filtered_files/`.  
   - Only valid dialogue or meaningful strings remain, ready for translation.  

3. **Repacking phase (`repack.py`)**  
   - Put original `.SCN` files in `input/` and translated `.txt` files in `filtered_files/`.  
   - Run `python repack.py` to generate repacked files in `repacked/`.  
   - The script updates pointers and preserves original file structure.  

## Requirements

- **Python 3.8+**  
- No external dependencies (only standard library modules).  

## Folder Structure

```
project_root/
│
├─ input/           # Original .SCN files
├─ output/          # Dumps produced by dump.py
├─ filtered_files/  # Cleaned files after refine.py (to translate)
├─ repacked/        # Final repacked .SCN files
│
├─ dump.py
├─ refine.py
└─ repack.py
```

## Usage

```bash
# 1. Dump SCN scripts
python dump.py

# 2. Refine extracted text
python refine.py

# 3. Repack translated text into SCN files
python repack.py
```

## Notes

- All scripts automatically create the required folders if they do not exist.  
- Encoding is handled as `latin-1` to preserve all byte values.  
- Control codes are represented as `<HEX=XX>` tags for easy editing.  
- No terminators are added during reinsertion — original data is reused.

## Additional Note – Editing the Game Font

If you need to add accented characters or other custom symbols, you can modify the game's font file:

Font file: ASCII16.FON

Format: 8×16 pixels, 4bpp (N64/MD tile format)

Recommended tool: CrystalTile2

This font file contains the character ascii used by the game. By editing it, you can insert accented letters (á, é, ó, etc.) or any other glyphs needed for translation.

## License

This project is released under the MIT License. You are free to use, modify, and share it, but attribution is appreciated.
