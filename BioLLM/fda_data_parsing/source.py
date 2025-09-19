import json

def generate_qa_pairs_from_sections(device_data):
    """파싱된 섹션에서 Q&A 쌍 생성"""
    qa_pairs = []
    
    k_number = device_data.get('k_number', 'Unknown')
    device_name = device_data.get('device_name', 'Unknown Device')
    parsed_sections = device_data.get('parsed_sections', {})
    
    if not parsed_sections:
        return qa_pairs
    
    # 1. Device Description -> Material Composition Q&A
    if parsed_sections.get('device_description'):
        desc = parsed_sections['device_description']
        
        qa_pairs.extend([
            {
                "messages": [
                    {"role": "user", "content": f"{k_number} 임플란트 시스템의 재료 구성을 분석해주세요."},
                    {"role": "assistant", "content": f"Device: {device_name}\n\n재료 구성 분석:\n{desc[:800]}..."}
                ]
            },
            {
                "messages": [
                    {"role": "user", "content": f"{device_name}에서 사용된 생체적합성 재료는 무엇인가요?"},
                    {"role": "assistant", "content": extract_materials_from_description(desc)}
                ]
            }
        ])
    
    # 2. Indications for Use -> Contact Classification Q&A
    if parsed_sections.get('indications_for_use'):
        indications = parsed_sections['indications_for_use']
        
        qa_pairs.extend([
            {
                "messages": [
                    {"role": "user", "content": f"이 의료기기의 생체적합성 요구사항은 무엇인가요?"},
                    {"role": "assistant", "content": generate_biocompatibility_requirements(indications, device_name)}
                ]
            },
            {
                "messages": [
                    {"role": "user", "content": f"{k_number}의 임상 적용 분야는?"},
                    {"role": "assistant", "content": f"적응증:\n{indications[:500]}..."}
                ]
            }
        ])
    
    # 3. Device Comparison -> Material Evolution Q&A
    if parsed_sections.get('device_comparison'):
        comparison = parsed_sections['device_comparison']
        
        qa_pairs.extend([
            {
                "messages": [
                    {"role": "user", "content": "기존 제품 대비 재료적 개선사항은 무엇인가요?"},
                    {"role": "assistant", "content": analyze_material_improvements(comparison)}
                ]
            },
            {
                "messages": [
                    {"role": "user", "content": "predicate device와의 생체적합성 비교 결과는?"},
                    {"role": "assistant", "content": f"비교 분석:\n{comparison[:600]}..."}
                ]
            }
        ])
    
    # 4. Performance Data -> Biocompatibility Validation Q&A
    if parsed_sections.get('performance_data'):
        performance = parsed_sections['performance_data']
        
        qa_pairs.extend([
            {
                "messages": [
                    {"role": "user", "content": f"이 재료의 생체적합성 검증 결과는?"},
                    {"role": "assistant", "content": extract_biocompatibility_results(performance)}
                ]
            },
            {
                "messages": [
                    {"role": "user", "content": "ISO 10993 테스트 결과를 요약해주세요."},
                    {"role": "assistant", "content": f"테스트 결과:\n{performance[:700]}..."}
                ]
            }
        ])
    
    return qa_pairs

def extract_materials_from_description(description):
    """Description에서 재료 정보 추출"""
    materials = []
    
    # 티타늄 관련
    if "titanium grade 4" in description.lower():
        materials.append("- Unalloyed Titanium Grade 4 (ASTM F67): 임플란트 본체용")
    if "ti-6al-4v" in description.lower():
        materials.append("- Titanium Alloy Ti-6Al-4V (ASTM F136): 어버트먼트 및 나사용")
    
    # 표면 처리
    if "anodized" in description.lower():
        materials.append("- Anodic oxidation (anodization): 표면 처리")
    if "dlc" in description.lower():
        materials.append("- DLC (Diamond Like Carbon) coating: 나사 표면 코팅")
    if "soluble salt" in description.lower():
        materials.append("- 가용성 염 보호층: 생체적합성 향상")
    
    return "\n".join(materials) if materials else f"재료 정보:\n{description[:400]}..."

def generate_biocompatibility_requirements(indications, device_name):
    """적응증에서 생체적합성 요구사항 생성"""
    requirements = []
    
    if "implant" in indications.lower():
        requirements.extend([
            "ISO 10993 분류: Implant (조직/뼈 접촉)",
            "접촉 지속시간: Permanent (30일 이상)",
            "필수 테스트:",
            "  • 세포독성 (ISO 10993-5)",
            "  • 감작성/자극성 (ISO 10993-10)", 
            "  • 유전독성 (ISO 10993-3)",
            "  • 임플란트 반응 (ISO 10993-6)",
            "  • 전신독성 (ISO 10993-11)"
        ])
    
    if "dental" in indications.lower():
        requirements.append("  • 구강 내 환경 적합성 검증 필요")
    
    return "\n".join(requirements) + f"\n\n원문:\n{indications[:300]}..."

def analyze_material_improvements(comparison):
    """비교 데이터에서 재료 개선사항 분석"""
    improvements = []
    
    if "tiultra" in comparison.lower():
        improvements.append("• TiUltra 표면 기술: 향상된 osseointegration")
    if "soluble salt" in comparison.lower():
        improvements.append("• 가용성 염 보호층 추가: 초기 치유 촉진")
    if "anodized" in comparison.lower():
        improvements.append("• Anodized 표면: 기존 machined 표면 대비 개선")
    if "conical connection" in comparison.lower():
        improvements.append("• Conical connection: 기계적 안정성 향상")
    
    return "\n".join(improvements) + f"\n\n상세 비교:\n{comparison[:400]}..."

def extract_biocompatibility_results(performance):
    """Performance data에서 생체적합성 결과 추출"""
    results = []
    
    if "iso 10993" in performance.lower():
        results.append("✓ ISO 10993-1 생체적합성 검증 완료")
    if "fatigue" in performance.lower():
        results.append("✓ 피로도 테스트 (ISO 14801) 통과")
    if "sterilization" in performance.lower():
        results.append("✓ 감마선 살균 검증 (SAL 10⁻⁶)")
    if "survival rate" in performance.lower():
        results.append("✓ 임상 생존율: 97.4% - 99.5%")
    if "endotoxin" in performance.lower():
        results.append("✓ 내독소 검사 통과")
    
    return "\n".join(results) + f"\n\n세부 결과:\n{performance[:500]}..."

def process_parsed_data_to_qa(input_jsonl, output_jsonl):
    """파싱된 FDA 데이터를 Q&A 형태로 변환"""
    
    with open(input_jsonl, 'r', encoding='utf-8') as infile, \
         open(output_jsonl, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            device_data = json.loads(line)
            
            # 파싱이 성공한 경우만 처리
            if device_data.get('parsing_status') == 'success':
                qa_pairs = generate_qa_pairs_from_sections(device_data)
                
                # 각 Q&A 쌍을 개별 줄로 저장
                for qa_pair in qa_pairs:
                    # 원본 메타데이터 추가
                    enhanced_qa = {
                        **qa_pair,
                        'source_k_number': device_data.get('k_number'),
                        'source_device_name': device_data.get('device_name'),
                        'source_date': device_data.get('decision_date')
                    }
                    outfile.write(json.dumps(enhanced_qa, ensure_ascii=False) + '\n')

def create_structured_json(input_jsonl, output_json):
    """구조화된 JSON 파일로 변환 (전체 데이터를 하나의 JSON으로)"""
    
    structured_data = {
        "dataset_info": {
            "name": "FDA 510k Biocompatibility QA Dataset",
            "description": "FDA 510(k) summary에서 추출한 생체적합성 재료 Q&A 데이터",
            "total_devices": 0,
            "total_qa_pairs": 0
        },
        "devices": []
    }
    
    with open(input_jsonl, 'r', encoding='utf-8') as infile:
        for line in infile:
            device_data = json.loads(line)
            
            if device_data.get('parsing_status') == 'success':
                qa_pairs = generate_qa_pairs_from_sections(device_data)
                
                device_entry = {
                    "k_number": device_data.get('k_number'),
                    "device_name": device_data.get('device_name'),
                    "decision_date": device_data.get('decision_date'),
                    "parsed_sections": device_data.get('parsed_sections'),
                    "qa_pairs": qa_pairs
                }
                
                structured_data["devices"].append(device_entry)
                structured_data["dataset_info"]["total_qa_pairs"] += len(qa_pairs)
        
        structured_data["dataset_info"]["total_devices"] = len(structured_data["devices"])
    
    with open(output_json, 'w', encoding='utf-8') as outfile:
        json.dump(structured_data, outfile, ensure_ascii=False, indent=2)
    
    print(f"구조화된 데이터 생성 완료:")
    print(f"- 총 기기 수: {structured_data['dataset_info']['total_devices']}")
    print(f"- 총 Q&A 쌍 수: {structured_data['dataset_info']['total_qa_pairs']}")

# 사용 예시
if __name__ == "__main__":
    input_file = 'processed_output_v2.jsonl'  # 파싱된 FDA 데이터
    
    # Option 1: Q&A JSONL 파일 생성 (각 Q&A가 한 줄씩)
    qa_output = 'biocompatibility_qa_dataset.jsonl'
    process_parsed_data_to_qa(input_file, qa_output)
    print(f"Q&A 데이터 생성 완료: {qa_output}")
    
    # Option 2: 구조화된 JSON 파일 생성 (전체를 하나의 JSON으로)
    json_output = 'biocompatibility_dataset.json'
    create_structured_json(input_file, json_output)
    print(f"구조화된 JSON 데이터 생성 완료: {json_output}")