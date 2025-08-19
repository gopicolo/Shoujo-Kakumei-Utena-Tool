import os
import glob
import re

# --- CONFIGURAÇÃO ---
# Pasta onde estão os arquivos .txt gerados pelo script de dump.
INPUT_FOLDER = "output"
# Pasta onde os arquivos .txt limpos e filtrados serão salvos.
OUTPUT_FOLDER = "filtered_files"

# --- REGRAS DO FILTRO ---
# 1. Proporção Mínima de Texto:
# Se a porcentagem de texto real (vs. códigos <HEX>) for menor que isso, a string é descartada.
# 0.3 significa que pelo menos 30% do conteúdo deve ser texto.
TEXT_TO_CODE_RATIO_THRESHOLD = 0.3

# 2. Máximo de Códigos de Controle:
# Strings com mais códigos <HEX> do que este valor serão descartadas.
MAX_CONTROL_CODES = 3

# 3. Mínimo de Caracteres Alfabéticos:
# Strings com menos letras do que este valor serão descartadas.
MIN_ALPHA_CHARS = 3

def filter_and_renumber_dump(raw_dump_path, final_output_path):
    """
    Lê um arquivo de dump, aplica filtros rigorosos para remover strings inválidas,
    e salva um novo arquivo limpo e renumerado.
    """
    print(f"--- Filtrando o arquivo: {os.path.basename(raw_dump_path)} ---")
    
    try:
        with open(raw_dump_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERRO: Arquivo de dump não encontrado: {raw_dump_path}"); return

    # Divide o arquivo em blocos usando o separador "####################################".
    blocks = content.split("####################################")
    
    candidate_blocks = []
    for block in blocks:
        block_content = block.strip()
        # Ignora blocos vazios ou que não sejam de string.
        if not block_content or "// STRING #" not in block_content:
            continue
        
        # Extrai o texto real da string para análise.
        text_content_match = re.search(r'\n\n(.*?)\n\n<END>', block, re.DOTALL)
        if not text_content_match:
            continue
        
        text_to_check = text_content_match.group(1)
        
        # --- APLICAÇÃO DOS FILTROS INICIAIS ---
        
        hex_tags = re.findall(r'<HEX=[0-9A-F]{2}>', text_to_check)
        
        if len(hex_tags) > MAX_CONTROL_CODES:
            continue

        clean_text = re.sub(r'<HEX=[0-9A-F]{2}>|\n', '', text_to_check).strip()
        
        if not clean_text:
            continue

        # FILTRO (NOVO): Exclui strings que são apenas números.
        if clean_text.isdigit():
            print(f"    -> REJEITADO (Apenas números): {clean_text[:40]}...")
            continue

        alpha_chars = re.findall(r'[a-zA-Z]', clean_text)
        if len(alpha_chars) < MIN_ALPHA_CHARS:
            continue

        if clean_text[0].islower() or clean_text[0] in ',.?!':
            continue

        num_hex_tags = len(hex_tags)
        num_text_chars = len(clean_text)
        
        total_tokens = num_text_chars + num_hex_tags
        if total_tokens == 0:
            continue

        ratio = num_text_chars / total_tokens
        if ratio < TEXT_TO_CODE_RATIO_THRESHOLD:
            continue

        # Se passou nos filtros iniciais, é um candidato.
        candidate_blocks.append({'block': block, 'clean_text': clean_text})

    # --- FILTRO DE SUBCONJUNTO (SUBSTRING) ---
    if not candidate_blocks:
        print("--> Nenhum bloco candidato passou na filtragem inicial.")
        return

    indices_to_remove = set()
    for i in range(len(candidate_blocks)):
        for j in range(len(candidate_blocks)):
            if i == j:
                continue
            
            text_i = candidate_blocks[i]['clean_text']
            text_j = candidate_blocks[j]['clean_text']
            
            # Se a string i for um pedaço da string j, e for mais curta, marca para remoção.
            if text_i in text_j and len(text_i) < len(text_j):
                print(f"    -> REJEITADO (Fragmento de outra string): {text_i[:40]}...")
                indices_to_remove.add(i)
                break # Já sabemos que precisa ser removida, podemos pular para a próxima string i.

    final_blocks = [candidate['block'] for i, candidate in enumerate(candidate_blocks) if i not in indices_to_remove]

    # Renumera e salva os blocos que passaram no filtro.
    with open(final_output_path, 'w', encoding='utf-8') as f_out:
        header_match = re.search(r"(// Dump .*? do arquivo:.*?)\n\n", content)
        if header_match:
            header = header_match.group(1).replace("Bruto do", "Filtrado do")
            f_out.write(header + "\n\n")
            
        f_out.write(f"// Total de strings de texto válidas: {len(final_blocks)}\n\n")
        
        for i, block in enumerate(final_blocks):
            renumbered_block = re.sub(r"// STRING #\d+", f"// STRING #{i + 1}", block)
            
            if "// Offset Original:" not in renumbered_block:
                original_offset_match = re.search(r"// String Offset: (0x[0-9A-F]{8})", block)
                if original_offset_match:
                    renumbered_block = re.sub(r"(// STRING #\d+)", r"\1\n" + f"// Offset Original: {original_offset_match.group(1)}", renumbered_block)

            f_out.write("####################################" + renumbered_block + "####################################\n\n")

    print(f"--> Arquivo final limpo e renumerado salvo em: {os.path.basename(final_output_path)}\n")


def main():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"Pasta '{INPUT_FOLDER}' criada. Por favor, coloque seus arquivos .txt de dump aqui.")
        return
        
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    search_path = os.path.join(INPUT_FOLDER, "*.txt")
    files_to_process = glob.glob(search_path)
    
    if not files_to_process:
        print(f"Nenhum arquivo '.txt' encontrado na pasta '{INPUT_FOLDER}'.")
        return
        
    for file_path in files_to_process:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        clean_base_name = base_name.replace("_raw_dump", "").replace("_dump", "")
        final_output_path = os.path.join(OUTPUT_FOLDER, f"{clean_base_name}.txt")
        
        filter_and_renumber_dump(file_path, final_output_path)

if __name__ == "__main__":
    main()
