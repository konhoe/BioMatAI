# 1. 라이브러리 임포트
import os
import re
import json
import fitz  # PyMuPDF 라이브러리

# 2. 핵심 로직을 담을 함수 정의

def extract_text_from_pdf(pdf_path):
    """PDF 파일 경로를 받아 전체 텍스트를 추출합니다."""
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        return full_text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return None

def find_510k_summary(full_text):
    """전체 text에서 '510(k) Summary' 섹션만 분리해냅니다. 가장 중요한 전처리 과정입니다."""
    # 정규표현식을 사용해 '510(k) Summary' 시작점을 찾습니다. 대소문자, 공백 차이를 고려합니다.
    match = re.search(r"510\(k\)\s+Summary", full_text, re.IGNORECASE)
    if not match:
        return None
    # Summary 시작점 이후의 텍스트만 잘라냅니다.
    summary_text = full_text[match.start():]
    return summary_text

def extract_structured_info(summary_text, k_number):
    """Summary 텍스트에서 'Device Name', 'Indications for Use' 등 항목별 정보를 추출합니다."""
    
    # 각 섹션의 시작을 알리는 키워드들입니다. (실제 문서에 맞게 추가/수정 필요)
    section_patterns = {
        "device_name": r"Trade\s*Name\s*:\s*(.*)",
        "indications_for_use": r"Indications\s+for\s+Use\s*:\s*(.*)",
        "device_description": r"Device\s+Description\s*:\s*(.*)",
        "predicate_comparison": r"Comparison\s+to\s+Predicate\s+Device\s*:\s*(.*)"
    }
    
    extracted_data = {"k_number": k_number}

    # 각 패턴을 순회하며 정보 추출
    for key, pattern in section_patterns.items():
        match = re.search(pattern, summary_text, re.IGNORECASE)
        if match:
            # 다음 섹션 시작 전까지의 내용을 추출하기 위한 로직이 필요합니다.
            # 간단한 예시로는 첫 번째 줄만 가져올 수 있습니다.
            # 실제로는 더 정교한 방법(다음 섹션 키워드 위치 찾기 등)이 필요합니다.
            extracted_data[key] = match.group(1).strip().split('\n')[0]
    
    return extracted_data

def generate_qa_pairs(info_dict):
    """추출된 정보를 바탕으로 Q&A 쌍을 생성합니다."""
    qa_pairs = []
    
    # 정보가 존재할 경우에만 Q&A 쌍을 생성
    if info_dict.get("device_name") and info_dict.get("indications_for_use"):
        question = f"What is the intended use for the device '{info_dict['device_name']}' (K-number: {info_dict['k_number']})?"
        answer = info_dict['indications_for_use']
        qa_pairs.append({"question": question, "answer": answer})

    if info_dict.get("device_name") and info_dict.get("device_description"):
        question = f"Can you describe the device '{info_dict['device_name']}'?"
        answer = info_dict['device_description']
        qa_pairs.append({"question": question, "answer": answer})
        
    # 다른 항목(예: predicate_comparison)에 대한 Q&A도 같은 방식으로 추가
        
    return qa_pairs

# 3. 메인 실행 블록
def main():
    pdf_directory = "input_pdfs"
    output_file = "output_dataset.json"
    final_dataset = []

    print("Starting PDF processing...")
    
    for filename in os.listdir(pdf_directory):
        if filename.endswith(".pdf"):
            k_number = filename.replace(".pdf", "")
            print(f"Processing {filename}...")
            
            pdf_path = os.path.join(pdf_directory, filename)
            
            # 1단계: 텍스트 추출
            full_text = extract_text_from_pdf(pdf_path)
            if not full_text:
                continue
                
            # 2단계: 510(k) Summary 섹션 분리
            summary_text = find_510k_summary(full_text)
            if not summary_text:
                print(f"  -> Warning: 510(k) Summary not found in {filename}.")
                continue
            
            # 3단계: 구조화된 정보 추출
            structured_info = extract_structured_info(summary_text, k_number)
            
            # 4단계: Q&A 생성
            qa_pairs = generate_qa_pairs(structured_info)
            
            if qa_pairs:
                final_dataset.extend(qa_pairs)

    # 최종 데이터셋을 JSON 파일로 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_dataset, f, indent=2, ensure_ascii=False)
        
    print(f"\nProcessing complete. {len(final_dataset)} Q&A pairs saved to {output_file}.")


if __name__ == "__main__":
    main()