import os
import pyrosetta
from pyrosetta.rosetta.core.pose import pose_from_pdb
from pyrosetta.rosetta.protocols.docking import DockMover, DockingInitialPerturbation
from pyrosetta.rosetta.core.scoring import get_score_function

def main():
    """
    메인 도킹 시뮬레이션 함수
    """
    # -------------------------------------------------------------------
    # ⚠️ 중요: 실행 전 필수 준비 사항
    # 1. PyRosetta 라이선스 발급 및 설치 완료
    # 2. Receptor PDB 파일 준비 (예: slab_receptor.pdb)
    #    - 금속 슬랩 CIF 파일을 PDB로 변환하고, Chain ID를 'A'로 설정
    # 3. Ligand PDB 파일 준비 (예: albumin_ligand.pdb)
    #    - 알부민 PDB를 다운로드하여 정리하고, Chain ID를 'B'로 설정
    # -------------------------------------------------------------------

    # --- 시뮬레이션 설정 ---
    RECEPTOR_PDB = "slab_receptor.pdb"
    LIGAND_PDB = "albumin_ligand.pdb"
    N_DECOYS = 1000  # 생성할 최종 구조 개수 (많을수록 좋음, 최소 1000개 권장)
    PARTNERS = "A_B" # Receptor Chain ID '_' Ligand Chain ID
    OUTPUT_DIR = "global_docking_results" # 결과가 저장될 폴더 이름
    # ---------------------------------------------------------

    print("--- PyRosetta 초기화 시작 ---")
    # high-resolution docking에 필요한 파라미터 로드
    pyrosetta.init(extra_options="-ex1 -ex2aro")
    print("--- PyRosetta 초기화 완료 ---")


    # --- 1. 입력 파일 로드 ---
    print(f"Receptor 파일 로드 중: {RECEPTOR_PDB}")
    receptor_pose = pose_from_pdb(RECEPTOR_PDB)

    print(f"Ligand 파일 로드 중: {LIGAND_PDB}")
    ligand_pose = pose_from_pdb(LIGAND_PDB)

    # 두 Pose를 하나로 합치기
    combined_pose = receptor_pose.clone()
    combined_pose.append_pose_by_jump(ligand_pose, 1)
    print("--- 입력 파일 로드 및 Pose 결합 완료 ---")


    # --- 2. 전역적 도킹 프로토콜 설정 ---
    # 1) 초기 위치를 무작위로 변경하는 Mover 준비
    randomize_mover = DockingInitialPerturbation()
    randomize_mover.set_partners(PARTNERS)
    randomize_mover.set_trans_magnitude(3.0)  # 3 Å 범위에서 무작위로 이동
    randomize_mover.set_rot_magnitude(8.0)   # 8도 범위에서 무작위로 회전

    # 2) 표준 Docking Mover 준비 (저해상도 탐색 + 고해상도 정밀화 동시 수행)
    dock_mover = DockMover()
    dock_mover.set_partners(PARTNERS)
    print("--- 도킹 프로토콜 설정 완료 ---")


    # --- 3. 시뮬레이션 실행 ---
    # 최종 점수 평가에 사용할 고해상도 점수 함수
    scorefxn_highres = pyrosetta.create_score_function("ref2015")
    
    # 여러 번의 도킹 작업을 관리하는 Job Distributor 설정
    job_distributor = pyrosetta.PyJobDistributor(OUTPUT_DIR, N_DECOYS, scorefxn_highres)
    
    print(f"--- 총 {N_DECOYS}개의 구조(Decoy) 생성 시작 ---")
    while not job_distributor.job_complete:
        print(f"--- Decoy {job_distributor.current_id} 생성 중... ---")
        
        # Pose를 초기 상태로 리셋
        current_pose = combined_pose.clone()
        
        # a. 리간드의 초기 위치를 무작위로 변경 (전역적 탐색의 핵심)
        randomize_mover.apply(current_pose)
        
        # b. 저해상도 & 고해상도 도킹 실행
        dock_mover.apply(current_pose)
        
        # c. 결과 구조(decoy)를 파일로 저장
        job_distributor.output_decoy(current_pose)

    print("✅ 전역적 도킹 시뮬레이션 완료!")
    print(f"결과는 '{OUTPUT_DIR}' 폴더에서 확인하세요.")


if __name__ == "__main__":
    main()