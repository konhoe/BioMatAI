import json
from datetime import datetime

def convert_jsonl_to_json(jsonl_file, json_file):
    """JSONL 파일을 JSON 파일로 변환"""
    
    data = {
        "metadata": {
            "converted_at": datetime.now().isoformat(),
            "source_file": jsonl_file,
            "total_records": 0,
            "successful_parsing": 0,
            "failed_parsing": 0
        },
        "records": []
    }
    
    with open(jsonl_file, 'r', encoding='utf-8') as infile:
        for line_num, line in enumerate(infile, 1):
            try:
                record = json.loads(line.strip())
                data["records"].append(record)
                
                # 파싱 상태 통계
                parsing_status = record.get('parsing_status')
                if parsing_status == 'success':
                    data["metadata"]["successful_parsing"] += 1
                elif parsing_status == 'no_summary_text':
                    data["metadata"]["failed_parsing"] += 1
                    
            except json.JSONDecodeError as e:
                print(f"Line {line_num}에서 JSON 파싱 오류: {e}")
                continue
    
    data["metadata"]["total_records"] = len(data["records"])
    
    # JSON 파일로 저장
    with open(json_file, 'w', encoding='utf-8') as outfile:
        json.dump(data, outfile, ensure_ascii=False, indent=2)
    
    print(f"변환 완료:")
    print(f"- 총 레코드: {data['metadata']['total_records']}")
    print(f"- 파싱 성공: {data['metadata']['successful_parsing']}")
    print(f"- 파싱 실패: {data['metadata']['failed_parsing']}")
    print(f"- 출력 파일: {json_file}")

def convert_jsonl_to_json_simple(jsonl_file, json_file):
    """JSONL을 단순 배열 형태 JSON으로 변환 (메타데이터 없이)"""
    
    records = []
    
    with open(jsonl_file, 'r', encoding='utf-8') as infile:
        for line in infile:
            try:
                record = json.loads(line.strip())
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류 (건너뜀): {e}")
                continue
    
    with open(json_file, 'w', encoding='utf-8') as outfile:
        json.dump(records, outfile, ensure_ascii=False, indent=2)
    
    print(f"단순 변환 완료: {len(records)}개 레코드 -> {json_file}")

# 사용 예시
if __name__ == "__main__":
    input_jsonl = 'processed_output.jsonl'  # 입력 JSONL 파일
    

    output_json_with_meta = 'fda_data_with_metadata.json'
    convert_jsonl_to_json(input_jsonl, output_json_with_meta)
