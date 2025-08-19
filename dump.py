import os
import struct
import glob
import string
import re

# --- CONFIGURAÇÃO ---
INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
FILE_EXTENSION = ".SCN"

# O endereço fixo do primeiro ponteiro, como você indicou.
ANCHOR_POINTER_OFFSET = 0x0A

# --- CONFIGURAÇÃO DO FILTRO ---
# Limite para o filtro: se a proporção de texto for menor que isso, a string é descartada.
# 0.3 significa que pelo menos 30% dos "tokens" (caracteres + tags) devem ser texto.
TEXT_TO_CODE_RATIO_THRESHOLD = 0.3
# Limite máximo de códigos de controle permitidos em uma string de texto válida.
MAX_CONTROL_CODES = 3

def format_string_with_codes(data, start_offset):
    """Lê uma string byte a byte, convertendo não-texto em tags <HEX> e 0E em quebra de linha."""
    result = ""
    pos = start_offset
    while pos < len(data) and data[pos] != 0:
        byte_val = data[pos]
        
        if byte_val == 0x0E:
            result += '\n'
        else:
            if 0x20 <= byte_val <= 0x7E or 0xA1 <= byte_val <= 0xDF:
                result += bytes([byte_val]).decode('latin-1')
            else:
                 result += f"<HEX={byte_val:02X}>"
        pos += 1
    return result

def dump_pointers_only(input_path, raw_output_path):
    """
    Extrai todas as strings que possuem ponteiros para um arquivo bruto.
    """
    print(f"--- Processando (Passo 1: Extração Bruta): {os.path.basename(input_path)} ---")
    
    try:
        with open(input_path, 'rb') as f: data = f.read()
    except FileNotFoundError:
        print(f"ERRO: Arquivo não encontrado {input_path}"); return False

    file_size = len(data)
    
    if ANCHOR_POINTER_OFFSET + 2 > file_size:
        print("ERRO: Arquivo muito pequeno para ler o ponteiro âncora."); return False
        
    first_string_offset = struct.unpack('<H', data[ANCHOR_POINTER_OFFSET:ANCHOR_POINTER_OFFSET+2])[0]
    
    pointer_area_end = first_string_offset
    text_area_start = first_string_offset
    
    print(f"Ponteiro âncora em 0x{ANCHOR_POINTER_OFFSET:X} aponta para 0x{first_string_offset:X}.")
    print(f"Área de Ponteiros definida: 0x00 - 0x{pointer_area_end:X}")

    string_map = {}
    
    for i in range(pointer_area_end - 2):
        ptr_val = struct.unpack('<H', data[i:i+2])[0]
        
        if ptr_val >= text_area_start and ptr_val < file_size and data.find(b'\x00', ptr_val) != -1:
            if ptr_val not in string_map:
                string_map[ptr_val] = []
            if i not in string_map[ptr_val]:
                string_map[ptr_val].append(i)

    if not string_map:
        print("--> Nenhum ponteiro válido encontrado na área definida."); return False

    sorted_string_offsets = sorted(string_map.keys())
    
    print(f"--> Mapeadas {len(sorted_string_offsets)} strings únicas.")

    with open(raw_output_path, 'w', encoding='utf-8') as f_out:
        f_out.write(f"// Dump Bruto do arquivo: {os.path.basename(input_path)}\n\n")

        for i, string_offset in enumerate(sorted_string_offsets):
            pointer_locs = sorted(string_map[string_offset])
            formatted_text = format_string_with_codes(data, string_offset)
            
            f_out.write("####################################\n")
            f_out.write(f"// STRING #{i + 1}\n")
            f_out.write(f"// String Offset: 0x{string_offset:08X}\n")
            for p_loc in pointer_locs:
                original_pointer_bytes = data[p_loc:p_loc+2].hex().upper()
                f_out.write(f"// -> Apontada por: 0x{p_loc:08X} (Valor: {original_pointer_bytes})\n")
            f_out.write(f"\n{formatted_text}\n\n<END>\n")
            f_out.write("####################################\n\n")
            
    print(f"--> Extração bruta concluída: {os.path.basename(raw_output_path)}")
    return True

def filter_and_renumber_dump(raw_dump_path, final_output_path):
    """Lê um arquivo de dump bruto, filtra o lixo e renumera as strings."""
    print(f"--- Processando (Passo 2: Filtragem e Limpeza): {os.path.basename(raw_dump_path)} ---")
    
    try:
        with open(raw_dump_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERRO: Arquivo de dump bruto não encontrado: {raw_dump_path}"); return

    blocks = content.split("####################################")
    
    filtered_blocks = []
    for block in blocks:
        block_content = block.strip()
        if not block_content or "// STRING #" not in block_content:
            continue
        
        text_content_match = re.search(r'\n\n(.*?)\n\n<END>', block, re.DOTALL)
        if not text_content_match: continue
        
        text_to_check = text_content_match.group(1)
        
        hex_tags = re.findall(r'<HEX=[0-9A-F]{2}>', text_to_check)
        
        if len(hex_tags) > MAX_CONTROL_CODES:
            continue

        clean_text = re.sub(r'<HEX=[0-9A-F]{2}>|\n', '', text_to_check).strip()
        
        if not clean_text: continue

        if len(clean_text) < 30 and clean_text[0].islower():
            continue

        num_hex_tags = len(hex_tags)
        num_text_chars = len(clean_text)
        
        total_tokens = num_text_chars + num_hex_tags
        if total_tokens == 0: continue

        ratio = num_text_chars / total_tokens
        if ratio < TEXT_TO_CODE_RATIO_THRESHOLD:
            continue

        filtered_blocks.append(block)

    with open(final_output_path, 'w', encoding='utf-8') as f_out:
        header_match = re.search(r"(// Dump Bruto do arquivo:.*?)\n\n", content)
        if header_match:
            header = header_match.group(1).replace("Dump Bruto do", "Dump Filtrado do")
            f_out.write(header + "\n\n")
            
        f_out.write(f"// Total de strings de texto válidas: {len(filtered_blocks)}\n\n")
        
        for i, block in enumerate(filtered_blocks):
            renumbered_block = re.sub(r"// STRING #\d+", f"// STRING #{i + 1}", block)
            original_offset_match = re.search(r"// String Offset: (0x[0-9A-F]{8})", block)
            if original_offset_match:
                renumbered_block = re.sub(r"(// STRING #\d+)", r"\1\n" + f"// Offset Original: {original_offset_match.group(1)}", renumbered_block)

            f_out.write("####################################" + renumbered_block + "####################################\n\n")

    print(f"--> Arquivo final limpo e renumerado salvo em: {os.path.basename(final_output_path)}")


def main():
    if not os.path.exists(INPUT_FOLDER): os.makedirs(INPUT_FOLDER)
    if not os.path.exists(OUTPUT_FOLDER): os.makedirs(OUTPUT_FOLDER)
    search_path = os.path.join(INPUT_FOLDER, f"*{FILE_EXTENSION}")
    files_to_process = glob.glob(search_path)
    if not files_to_process: print(f"Nenhum arquivo '{FILE_EXTENSION}' encontrado na pasta '{INPUT_FOLDER}'.")
    for file_path in files_to_process:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        raw_output_path = os.path.join(OUTPUT_FOLDER, f"{base_name}_raw_dump.txt")
        final_output_path = os.path.join(OUTPUT_FOLDER, f"{base_name}.txt")
        
        # Passo 1: Extrai tudo para um arquivo bruto.
        success = dump_pointers_only(file_path, raw_output_path)
        
        # Passo 2: Se a extração foi bem-sucedida, filtra o arquivo bruto.
        if success:
            filter_and_renumber_dump(raw_output_path, final_output_path)
            os.remove(raw_output_path) # Remove o arquivo bruto para manter a pasta limpa.
            print(f"--> Processo concluído para {base_name}. O arquivo final é '{os.path.basename(final_output_path)}'.\n")

if __name__ == "__main__":
    main()
