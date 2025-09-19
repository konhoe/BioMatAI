#!/usr/bin/env python3
"""
작은 단백질 생성 스크립트
알부민의 일부를 추출하여 테스트용 작은 단백질 생성
"""

def extract_albumin_domain(pdb_file, fasta_file, start_res=1, end_res=80, output_dir="../input/proteins/"):
    """
    알부민 PDB에서 특정 영역만 추출
    
    Args:
        pdb_file: 원본 알부민 PDB 파일
        fasta_file: 원본 알부민 FASTA 파일  
        start_res: 시작 잔기 번호
        end_res: 끝 잔기 번호
        output_dir: 출력 디렉토리
    """
    import os
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # FASTA 시퀀스 읽기
    with open(fasta_file, 'r') as f:
        lines = f.readlines()
    
    sequence = ""
    for line in lines:
        if not line.startswith('>'):
            sequence += line.strip()
    
    # 작은 서열 추출
    small_sequence = sequence[start_res-1:end_res]
    
    print(f"원본 알부민 길이: {len(sequence)}")
    print(f"추출된 영역: {start_res}-{end_res}")
    print(f"작은 단백질 길이: {len(small_sequence)}")
    print(f"추출된 서열: {small_sequence}")
    
    # 작은 FASTA 파일 생성
    small_fasta_path = os.path.join(output_dir, "small_albumin.fasta")
    with open(small_fasta_path, 'w') as f:
        f.write(f">small_albumin_domain_{start_res}_{end_res}\n")
        f.write(f"{small_sequence}\n")
    
    # PDB 파일에서 해당 잔기들만 추출
    small_pdb_path = os.path.join(output_dir, "small_albumin.pdb")
    with open(pdb_file, 'r') as f:
        pdb_lines = f.readlines()
    
    with open(small_pdb_path, 'w') as f:
        for line in pdb_lines:
            if line.startswith('ATOM') and line[21] == 'A':  # 알부민 체인 A
                res_num = int(line[22:26].strip())
                if start_res <= res_num <= end_res:
                    # 잔기 번호를 1부터 시작하도록 재조정
                    new_res_num = res_num - start_res + 1
                    new_line = line[:22] + f"{new_res_num:4d}" + line[26:]
                    f.write(new_line)
            elif line.startswith('HETATM'):  # 금속 표면은 그대로 유지
                f.write(line)
            elif line.startswith(('HEADER', 'TITLE', 'REMARK')):
                f.write(line)
    
    print(f"생성된 파일들:")
    print(f"  FASTA: {small_fasta_path}")
    print(f"  PDB: {small_pdb_path}")
    
    return small_fasta_path, small_pdb_path

def create_insulin_test():
    """
    Insulin 단백질 생성 (51개 아미노산)
    """
    # Human insulin sequence
    insulin_sequence = "GIVEQCCTSICSLYQLENYCNFVNQHLCGSHLVEALYLVCGERGFFYTPKT"
    
    fasta_path = "input/proteins/insulin.fasta"
    with open(fasta_path, 'w') as f:
        f.write(">insulin_human\n")
        f.write(f"{insulin_sequence}\n")
    
    print(f"Insulin 테스트 파일 생성:")
    print(f"  길이: {len(insulin_sequence)}")
    print(f"  파일: {fasta_path}")
    
    return fasta_path

def create_ubiquitin_test():
    """
    Ubiquitin 단백질 생성 (76개 아미노산)
    """
    # Human ubiquitin sequence
    ubiquitin_sequence = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
    
    fasta_path = "input/proteins/ubiquitin.fasta"
    with open(fasta_path, 'w') as f:
        f.write(">ubiquitin_human\n")
        f.write(f"{ubiquitin_sequence}\n")
    
    print(f"Ubiquitin 테스트 파일 생성:")
    print(f"  길이: {len(ubiquitin_sequence)}")
    print(f"  파일: {fasta_path}")
    
    return fasta_path

if __name__ == "__main__":
    import sys
    import os
    
    print("작은 단백질 생성 옵션:")
    print("1. 알부민 도메인 추출 (1-80 잔기)")
    print("2. Insulin (51개 아미노산)")
    print("3. Ubiquitin (76개 아미노산)")
    
    choice = input("선택하세요 (1/2/3): ").strip()
    
    if choice == "1":
        albumin_pdb = "../input/proteins/albumin.pdb"
        albumin_fasta = "../input/proteins/protein.fasta"
        
        if os.path.exists(albumin_pdb) and os.path.exists(albumin_fasta):
            extract_albumin_domain(albumin_pdb, albumin_fasta)
        else:
            print(f"파일을 찾을 수 없습니다:")
            print(f"  {albumin_pdb}")
            print(f"  {albumin_fasta}")
    
    elif choice == "2":
        create_insulin_test()
    
    elif choice == "3":
        create_ubiquitin_test()
    
    else:
        print("잘못된 선택입니다.")