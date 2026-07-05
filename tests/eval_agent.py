import sys
import os
from unittest.mock import patch, MagicMock

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set a dummy key if not present so backend validation passes
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "mock-api-key"

# Create a mock Gemini client instance and response
mock_client_instance = MagicMock()
mock_response = MagicMock()
mock_response.text = "## Mock Safety Report\nThis is a mocked safe report for testing."
mock_client_instance.models.generate_content.return_value = mock_response

@patch("google.genai.Client", return_value=mock_client_instance)
def run_evaluations(mock_genai_client, *args):
    from backend.agents.agent_system import analyze_ingredient
    
    print("=" * 60)
    print("        MediSafe Agent Local Evaluations Suite (Day 4)")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "Test Case 1: Safe Drug (Acetaminophen)",
            "ingredient": "Acetaminophen",
            "bypass": False,
            "expected_status": "normal"
        },
        {
            "name": "Test Case 2: Allergic Drug (Aspirin) - Expecting Triage Block",
            "ingredient": "Aspirin",
            "bypass": False,
            "expected_status": "requires_triage"
        },
        {
            "name": "Test Case 3: Allergic Drug (Aspirin) with Pharmacist Override",
            "ingredient": "Aspirin",
            "bypass": True,
            "expected_status": "normal"
        }
    ]
    
    passed_tests = 0
    
    for tc in test_cases:
        print(f"\n[RUNNING] {tc['name']}...")
        try:
            result = analyze_ingredient(tc["ingredient"], bypass_triage=tc["bypass"])
            
            actual_status = result.get("status", "normal")
            
            if actual_status == tc["expected_status"]:
                print(f"[PASSED] Correctly handled {tc['ingredient']} (Status: {actual_status})")
                passed_tests += 1
            else:
                print(f"[FAILED] Expected {tc['expected_status']}, but got {actual_status}")
                
            # If normal, check if report content was generated
            if actual_status == "normal":
                if "report" in result and len(result["report"]) > 0:
                    print("         -> Success: Safety report generated.")
                else:
                    print("         -> Failure: Safety report was empty.")
                    
        except Exception as e:
            print(f"[ERROR] Test threw an exception: {str(e)}")
            
    print("\n" + "=" * 60)
    print(f" EVALUATION SUMMARY: {passed_tests}/{len(test_cases)} Passed")
    print("=" * 60)
    
    if passed_tests == len(test_cases):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_evaluations()
