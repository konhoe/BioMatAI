import json
import re

def check_summary_availability(jsonl_file):
    """summary_text가 있는 레코드와 없는 레코드 확인"""
    with_summary = []
    without_summary = []
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data.get('summary_text') and data['summary_text'].strip():
                with_summary.append(data)
            else:
                without_summary.append(data)
    
    print(f"Summary text 있음: {len(with_summary)}개")
    print(f"Summary text 없음: {len(without_summary)}개")
    
    return with_summary, without_summary

def get_summary_alternatives(data_record):
    """summary_text가 없을 때 대안 방법들"""
    alternatives = []
    
    # Option 1: detail_link에서 크롤링
    if data_record.get('detail_link'):
        alternatives.append(f"크롤링 가능: {data_record['detail_link']}")
    
    # Option 2: FDA API 사용
    k_number = data_record.get('k_number')
    if k_number:
        api_url = f"https://api.fda.gov/device/510k.json?search=k_number:{k_number}"
        alternatives.append(f"FDA API: {api_url}")
    
    # Option 3: PDF 직접 다운로드 시도
    pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{k_number[1:3]}/{k_number}.pdf"
    alternatives.append(f"직접 PDF: {pdf_url}")
    
    return alternatives

SECTION_PATTERNS = {
    'device_description': [
        r'1\.4\s+Device Description',
        r'Device Description Summary',
        r'DEVICE\s+DESCRIPTION\s+SUMMARY',
        r'1\.4.*Device.*Description',
        r'Subject Device.*is composed of',
        r'DEVICE\s+DESCRIPTION',
        r'Description\s+of\s+the\s+Device'
    ],
    'indications_for_use': [
        r'1\.5\s+Intended Use/Indication for Use',
        r'1\.5.*Intended.*Use',
        r'Indications for Use \(Describe\)',
        r'INDICATIONS\s+FOR\s+USE.*intended.*to.*be.*surgically.*placed',
        r'NobelZygoma.*TiUltra.*implants.*are.*endosseous',
        r'INDICATIONS\s+FOR\s+USE',
        r'Intended\s+Use.*Indication'
    ],
    'device_comparison': [
        r'1\.7\s+Technological Comparison',
        r'1\.7.*Technological.*Comparison',
        r'Substantial Equivalence Table',
        r'COMPARISON.*PREDICATE',
        r'Subject Device.*Primary Predicate Device',
        r'SUBSTANTIAL\s+EQUIVALENCE',
        r'Device\s+Comparison'
    ],
    'performance_data': [
        r'1\.8\s+Non-Clinical.*Tests Summary',
        r'1\.8.*Non-Clinical.*Tests',
        r'Summary of Non-Clinical Testing',
        r'Non-clinical testing was performed',
        r'PERFORMANCE\s+DATA',
        r'NON-CLINICAL\s+RESULTS',
        r'BIOCOMPATIBILITY.*testing',
        r'fatigue performance.*was evaluated'
    ]
}

def find_section_text(summary_text, patterns):
    """패턴을 사용해서 해당 섹션의 텍스트 추출"""
    
    # 먼저 섹션별 번호 기반 추출 시도 (1.4, 1.5, 1.7, 1.8)
    section_number_patterns = {
        'device_description': r'1\.4.*?(?=1\.5|1\.6|1\.7|$)',
        'indications_for_use': r'1\.5.*?(?=1\.6|1\.7|$)',
        'device_comparison': r'1\.7.*?(?=1\.8|2\.|$)',
        'performance_data': r'1\.8.*?(?=2\.|3\.|Conclusion|$)'
    }
    
    # 패턴에 해당하는 섹션 번호가 있는지 확인
    for section_key, number_pattern in section_number_patterns.items():
        # 현재 찾고 있는 섹션인지 확인 (patterns 리스트에서 해당 섹션 키워드 포함 여부)
        if any(section_key.replace('_', '') in pattern.lower().replace('\\s+', ' ').replace('.*', '') for pattern in patterns):
            number_match = re.search(number_pattern, summary_text, re.DOTALL | re.IGNORECASE)
            if number_match:
                section_text = number_match.group(0).strip()
                # 섹션 제목 제거 후 내용만 반환
                section_text = re.sub(r'^1\.\d+[^\n]*\n?', '', section_text, flags=re.MULTILINE).strip()
                if len(section_text) > 50:  # 의미있는 내용이 있는 경우만
                    return clean_section_text(section_text)
    
    # 번호 기반으로 찾지 못한 경우 기존 키워드 기반 방식 사용
    for pattern in patterns:
        # 섹션 시작 부분 찾기
        start_match = re.search(pattern, summary_text, re.IGNORECASE)
        if start_match:
            start_pos = start_match.end()
            
            # 다음 섹션까지의 텍스트 추출
            all_other_patterns = []
            for other_section, other_patterns in SECTION_PATTERNS.items():
                all_other_patterns.extend(other_patterns)
            
            # 현재 패턴은 제외
            all_other_patterns = [p for p in all_other_patterns if p not in patterns]
            
            # 가장 가까운 다음 섹션 찾기
            end_pos = len(summary_text)
            for next_pattern in all_other_patterns:
                next_match = re.search(next_pattern, summary_text[start_pos:], re.IGNORECASE)
                if next_match:
                    potential_end = start_pos + next_match.start()
                    if potential_end < end_pos:
                        end_pos = potential_end
            
            # 텍스트 추출 및 정리
            section_text = summary_text[start_pos:end_pos].strip()
            if section_text:
                return clean_section_text(section_text)
    
    return None

def clean_section_text(text):
    """섹션 텍스트 정리"""
    # 연속된 빈 라인 제거
    text = re.sub(r'\n\s*\n', '\n', text)
    # 과도한 공백 정리 (하지만 문단 구분은 유지)
    text = re.sub(r'[ \t]+', ' ', text)
    # 페이지 번호나 헤더 제거
    text = re.sub(r'Page \d+ of \d+', '', text)
    text = re.sub(r'K\d{6}.*?Page.*?\d+', '', text)
    
    return text.strip()

def extract_sections_from_summary(summary_text):
    """summary_text에서 4개 섹션 추출"""
    if not summary_text or summary_text.strip() == "":
        return None
    
    sections = {
        'device_description': None,
        'indications_for_use': None, 
        'device_comparison': None,
        'performance_data': None
    }
    
    # 각 섹션별로 텍스트 추출 시도
    for section_name, patterns in SECTION_PATTERNS.items():
        sections[section_name] = find_section_text(summary_text, patterns)
    
    return sections

def process_fda_data(jsonl_input_file, jsonl_output_file):
    """전체 데이터 처리 파이프라인"""
    processed_count = 0
    
    with open(jsonl_input_file, 'r', encoding='utf-8') as infile, \
         open(jsonl_output_file, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            original_data = json.loads(line)
            
            # Summary text 확인
            summary_text = original_data.get('summary_text')
            
            if summary_text and summary_text.strip():
                # 섹션 추출
                sections = extract_sections_from_summary(summary_text)
                
                # 기존 데이터에 섹션 정보 추가
                enhanced_data = {
                    **original_data,
                    'parsed_sections': sections,
                    'parsing_status': 'success'
                }
                processed_count += 1
            else:
                # Summary text 없는 경우
                enhanced_data = {
                    **original_data,
                    'parsed_sections': None,
                    'parsing_status': 'no_summary_text'
                }
            
            # 결과 저장
            outfile.write(json.dumps(enhanced_data, ensure_ascii=False) + '\n')
    
    print(f"총 {processed_count}개 레코드 처리 완료")

# 사용 예시
if __name__ == "__main__":
    # 1. 먼저 데이터 상태 확인
    with_summary, without_summary = check_summary_availability('fda_implant.jsonl')
    
    # 2. 데이터 처리
    process_fda_data('fda_implant.jsonl', 'processed_output.jsonl')
    
    # 3. 결과 확인 (처음 몇 개만 출력)
    with open('processed_output.jsonl', 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 3:  # 처음 3개만 확인
                break
            data = json.loads(line)
            print(f"K-number: {data['k_number']}")
            if data['parsed_sections']:
                for section, content in data['parsed_sections'].items():
                    if content:
                        print(f"  {section}: {content[:100]}...")
            print("---")