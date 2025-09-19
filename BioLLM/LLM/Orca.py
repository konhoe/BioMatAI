import os
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    BitsAndBytesConfig
)
from huggingface_hub import login
import gc

def setup_environment():
    """환경 설정 및 CUDA 확인"""
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"GPU {i} Memory: {torch.cuda.get_device_properties(i).total_memory / 1e9:.1f} GB")
    else:
        print("WARNING: CUDA not available. CPU-only training will be extremely slow.")

def login_huggingface(token=None):
    """Hugging Face 로그인"""
    if token:
        login(token=token)
        print("Hugging Face login successful with provided token")
    else:
        try:
            login()  # 저장된 토큰 사용
            print("Hugging Face login successful with saved token")
        except:
            print("Please login to Hugging Face or provide token")
            print("Run: huggingface-cli login")
            return False
    return True

def download_model_full_precision(model_name="microsoft/Orca-2-7b", cache_dir="./models"):
    """전체 정밀도로 모델 다운로드"""
    print(f"Downloading {model_name} in full precision...")
    
    # 토크나이저 다운로드
    print("Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        trust_remote_code=True
    )
    
    # 모델 다운로드 (CPU에 로드하여 메모리 절약)
    print("Downloading model (loading to CPU first)...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        torch_dtype=torch.float16,  # 메모리 절약을 위해 FP16
        device_map="cpu",  # 먼저 CPU에 로드
        trust_remote_code=True,
        low_cpu_mem_usage=True
    )
    
    print(f"Model successfully downloaded to: {cache_dir}")
    return tokenizer, model

def download_model_8bit(model_name="microsoft/Orca-2-7b", cache_dir="./models"):
    """8비트 양자화로 모델 다운로드 (메모리 절약)"""
    print(f"Downloading {model_name} with 8-bit quantization...")
    
    # 8비트 설정
    bnb_config = BitsAndBytesConfig(
        load_in_8bit=True,
        bnb_8bit_use_double_quant=True,
        bnb_8bit_quant_type="nf8",
        bnb_8bit_compute_dtype=torch.bfloat16
    )
    
    # 토크나이저
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        trust_remote_code=True
    )
    
    # 8비트 양자화된 모델
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    
    print("Model loaded with 8-bit quantization")
    return tokenizer, model

def download_model_4bit(model_name="microsoft/Orca-2-7b", cache_dir="./models"):
    """4비트 양자화로 모델 다운로드 (최대 메모리 절약)"""
    print(f"Downloading {model_name} with 4-bit quantization...")
    
    # 4비트 설정
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    
    # 토크나이저
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        trust_remote_code=True
    )
    
    # 4비트 양자화된 모델
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    
    print("Model loaded with 4-bit quantization")
    return tokenizer, model

def move_model_to_gpu(model):
    """모델을 GPU로 이동"""
    if torch.cuda.is_available():
        print("Moving model to GPU...")
        model = model.to('cuda')
        print("Model moved to GPU successfully")
    else:
        print("CUDA not available, keeping model on CPU")
    return model

def clear_memory():
    """메모리 정리"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("GPU memory cleared")

def test_model_inference(tokenizer, model, test_prompt="Explain biocompatibility in medical devices."):
    """간단한 추론 테스트"""
    print(f"\nTesting model with prompt: '{test_prompt}'")
    
    # 입력 토큰화
    inputs = tokenizer(test_prompt, return_tensors="pt")
    if torch.cuda.is_available() and next(model.parameters()).is_cuda:
        inputs = {k: v.to('cuda') for k, v in inputs.items()}
    
    # 추론
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    # 결과 디코딩
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"Model response:\n{response}")

def main():
    """메인 파이프라인"""
    print("=== Orca 2 Model Download Pipeline ===\n")
    
    # 1. 환경 설정
    setup_environment()
    
    # 2. Hugging Face 로그인
    if not login_huggingface():
        return
    
    # 3. 모델 선택
    model_options = {
        "1": "microsoft/Orca-2-7b",
        "2": "microsoft/Orca-2-13b"
    }
    
    print("\nSelect model:")
    for key, value in model_options.items():
        print(f"{key}: {value}")
    
    choice = input("Enter choice (1 or 2): ").strip()
    model_name = model_options.get(choice, "microsoft/Orca-2-7b")
    print(f"Selected model: {model_name}")
    
    # 4. 다운로드 방식 선택
    print("\nSelect download method:")
    print("1: Full precision (FP16) - Best quality, most memory")
    print("2: 8-bit quantization - Balanced")
    print("3: 4-bit quantization - Least memory, some quality loss")
    
    method_choice = input("Enter choice (1, 2, or 3): ").strip()
    
    try:
        # 5. 모델 다운로드
        cache_dir = "./orca2_models"
        os.makedirs(cache_dir, exist_ok=True)
        
        if method_choice == "1":
            tokenizer, model = download_model_full_precision(model_name, cache_dir)
            model = move_model_to_gpu(model)
        elif method_choice == "2":
            tokenizer, model = download_model_8bit(model_name, cache_dir)
        else:  # 기본값은 4bit
            tokenizer, model = download_model_4bit(model_name, cache_dir)
        
        print("\n=== Download Complete ===")
        print(f"Model: {model_name}")
        print(f"Cache directory: {cache_dir}")
        print(f"Model parameters: {model.num_parameters():,}")
        
        # 6. 메모리 사용량 체크
        if torch.cuda.is_available():
            print(f"GPU memory allocated: {torch.cuda.memory_allocated() / 1e9:.1f} GB")
            print(f"GPU memory reserved: {torch.cuda.memory_reserved() / 1e9:.1f} GB")
        
        # 7. 간단한 테스트
        test_inference = input("\nRun inference test? (y/n): ").strip().lower()
        if test_inference == 'y':
            test_model_inference(tokenizer, model)
        
        # 8. 모델 저장 (선택사항)
        save_local = input("\nSave model locally for future use? (y/n): ").strip().lower()
        if save_local == 'y':
            save_path = f"./saved_models/{model_name.replace('/', '_')}"
            os.makedirs(save_path, exist_ok=True)
            tokenizer.save_pretrained(save_path)
            model.save_pretrained(save_path)
            print(f"Model saved to: {save_path}")
        
        return tokenizer, model
        
    except Exception as e:
        print(f"Error during download: {e}")
        clear_memory()
        return None, None

if __name__ == "__main__":
    # 필요한 패키지 설치 확인
    required_packages = [
        "transformers>=4.35.0",
        "torch>=2.0.0", 
        "accelerate>=0.20.0",
        "bitsandbytes>=0.41.0",
        "huggingface_hub>=0.16.0"
    ]
    
    print("Required packages:")
    for pkg in required_packages:
        print(f"  pip install {pkg}")
    print()
    
    # 실행
    tokenizer, model = main()