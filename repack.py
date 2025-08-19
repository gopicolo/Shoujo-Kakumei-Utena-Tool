import os
import glob
import re
import struct

# --- CONFIGURAÇÃO ---
# Pasta com os arquivos .SCN originais.
ORIGINAL_FOLDER = "input"
# Pasta com os arquivos .txt traduzidos e filtrados.
TEXT_FOLDER = "filtered_files"
# Pasta onde os novos arquivos .SCN serão salvos.
REPACK_FOLDER = "repacked"

def parse_filtered_txt(txt_path):
    """
    Lê um arquivo de texto filtrado e extrai as strings e seus ponteiros originais.
    Retorna uma lista de dicionários, cada um representando uma string.
    """
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return None

    strings_info = []
    blocks = content.split("####################################")

    for block in blocks:
        if not block.strip() or "// STRING #" not in block:
            continue

        # Extrai o offset original da string.
        original_offset_match = re.search(r"// String Offset:\s+(0x[0-9A-F]{8})", block, re.IGNORECASE)
        if not original_offset_match:
            continue
        
        original_offset = int(original_offset_match.group(1), 16)
        
        # Extrai todos os locais de ponteiros que apontavam para esta string.
        pointer_locs = [int(loc, 16) for loc in re.findall(r"// -> Apontada por:\s+(0x[0-9A-F]{8})", block, re.IGNORECASE)]
        
        # Extrai o conteúdo do texto.
        text_content_match = re.search(r'\n\n(.*?)\n\n<END>', block, re.DOTALL)
        if not text_content_match:
            continue
            
        text_content = text_content_match.group(1)
        
        strings_info.append({
            'original_offset': original_offset,
            'pointer_locs': pointer_locs,
            'text': text_content
        })
        
    # Ordena as strings pelo seu offset original para processá-las na ordem correta.
    strings_info.sort(key=lambda x: x['original_offset'])
    return strings_info

def convert_text_to_bytes(text):
    """Converte o texto do script de volta para a sua forma em bytes."""
    # Substitui quebras de linha pelo byte 0x0E.
    text = text.replace('\n', chr(0x0E))
    
    # Converte as tags <HEX=..> de volta para bytes.
    def hex_replacer(match):
        hex_value = int(match.group(1), 16)
        return chr(hex_value)
        
    text = re.sub(r'<HEX=([0-9A-F]{2})>', hex_replacer, text, flags=re.IGNORECASE)
    
    # Codifica o resultado final usando 'latin-1' para preservar todos os bytes.
    return text.encode('latin-1')

def find_end_of_string_block(data, start_offset):
    """Encontra o fim de uma string e pula todos os bytes nulos de preenchimento."""
    end_null = data.find(b'\x00', start_offset)
    if end_null == -1: 
        return len(data)
    pos = end_null + 1
    while pos < len(data) and data[pos] == 0:
        pos += 1
    return pos

def repack_file(txt_path, original_scn_path, output_scn_path):
    """
    Reconstrói um arquivo .SCN usando o texto de um arquivo .txt, preservando os dados órfãos.
    NOVA LÓGICA: não adiciona terminador; apenas insere o texto e reaproveita
    do arquivo original os bytes de terminador/padding entre as strings.
    """
    print(f"--- Repack: {os.path.basename(txt_path)} -> {os.path.basename(output_scn_path)} ---")

    strings_info = parse_filtered_txt(txt_path)
    if not strings_info:
        print("ERRO: Não foi possível ler ou parsear o arquivo de texto.")
        return

    try:
        with open(original_scn_path, 'rb') as f:
            original_data = f.read()
    except FileNotFoundError:
        print(f"ERRO: Arquivo .SCN original não encontrado: {original_scn_path}")
        return

    file_end = len(original_data)

    # 1. Separa o bloco de código/ponteiros original.
    first_string_original_offset = strings_info[0]['original_offset']
    pointer_block = bytearray(original_data[:first_string_original_offset])
    
    # 2. Reconstrói o bloco de texto, inserindo o texto traduzido e preservando
    # exatamente os bytes de terminador/padding/orfãos que já existiam no original.
    new_text_block = bytearray()
    new_pointer_map = {}  # Mapeia {offset_original -> offset_novo}
    current_new_offset = first_string_original_offset

    for i, string_info in enumerate(strings_info):
        original_offset = string_info['original_offset']
        new_pointer_map[original_offset] = current_new_offset

        # Próxima string no original (ou EOF se for a última)
        if i + 1 < len(strings_info):
            next_start = strings_info[i+1]['original_offset']
        else:
            next_start = file_end

        # Converte texto traduzido (sem adicionar terminador)
        text_bytes = convert_text_to_bytes(string_info['text'])
        new_text_block.extend(text_bytes)
        current_new_offset += len(text_bytes)

        # Localiza o primeiro 0x00 após o texto original (início do terminador original)
        first_zero = original_data.find(b'\x00', original_offset)

        # Copia do primeiro 0x00 até o início da próxima string (preserva terminador+padding+qualquer dado no meio)
        if first_zero != -1 and first_zero < next_start:
            tail = original_data[first_zero:next_start]
            new_text_block.extend(tail)
            current_new_offset += len(tail)
        else:
            # Caso raro: sem 0x00 antes da próxima string. Não insere nada (respeita “não adicionar terminador”).
            pass

    print(f"--> Bloco de texto reconstruído. Novo tamanho: {len(new_text_block)} bytes.")

    # 3. Atualiza todos os ponteiros no bloco de ponteiros (little-endian 2 bytes).
    pointers_updated = 0
    for string_info in strings_info:
        original_offset = string_info['original_offset']
        new_offset = new_pointer_map.get(original_offset)
        if new_offset is not None:
            new_pointer_bytes = struct.pack('<H', new_offset)
            for loc in string_info['pointer_locs']:
                if loc + 2 <= len(pointer_block):
                    pointer_block[loc:loc+2] = new_pointer_bytes
                    pointers_updated += 1
    
    print(f"--> {pointers_updated} ponteiros foram recalculados e atualizados.")

    # 4. Junta os blocos e salva o novo arquivo.
    final_data = bytes(pointer_block) + bytes(new_text_block)
    with open(output_scn_path, 'wb') as f_out:
        f_out.write(final_data)
        
    print(f"--> Arquivo repacked salvo com sucesso em: {output_scn_path}\n")

def main():
    for folder in [ORIGINAL_FOLDER, TEXT_FOLDER, REPACK_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Pasta '{folder}' criada.")

    search_path = os.path.join(TEXT_FOLDER, "*.txt")
    text_files = glob.glob(search_path)
    
    if not text_files:
        print(f"Nenhum arquivo .txt encontrado na pasta '{TEXT_FOLDER}'.")
        return
        
    for txt_path in text_files:
        base_name = os.path.splitext(os.path.basename(txt_path))[0]
        
        original_scn_path = os.path.join(ORIGINAL_FOLDER, f"{base_name}.SCN")
        output_scn_path = os.path.join(REPACK_FOLDER, f"{base_name}.SCN")
        
        repack_file(txt_path, original_scn_path, output_scn_path)

if __name__ == "__main__":
    main()
