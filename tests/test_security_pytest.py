import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add the project root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set dummy key so validation passes
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "mock-api-key"

# Define mock response object
mock_client_instance = MagicMock()
mock_response = MagicMock()
mock_response.text = '{"safety_level": "safe", "pill_type": "tablet", "pill_color": "white", "food_warnings": {"alcohol": "avoid", "dairy": "safe", "grapefruit": "safe", "caffeine": "safe"}, "report": "This is a mocked safety report."}'
mock_client_instance.models.generate_content.return_value = mock_response

@pytest.fixture(autouse=True)
def mock_gemini():
    """Automatically mock Gemini client for all tests."""
    with patch("google.genai.Client", return_value=mock_client_instance):
        yield

def test_safe_drug_acetaminophen():
    """Test that a non-allergic drug returns normal status and generates report content."""
    from backend.agents.agent_system import analyze_ingredient
    result = analyze_ingredient("Acetaminophen", bypass_triage=False)
    
    assert result["status"] == "normal"
    assert "report" in result
    assert result["ingredient"] == "Acetaminophen"
    assert result["safety_level"] == "safe"
    assert result["pill_type"] == "tablet"
    assert result["pill_color"] == "white"

def test_allergic_drug_aspirin_blocks():
    """Test that a drug matching user allergies is blocked and requires pharmacist triage."""
    from backend.agents.agent_system import analyze_ingredient
    result = analyze_ingredient("Aspirin", bypass_triage=False)
    
    assert result["status"] == "requires_triage"
    assert "allergies" in result
    assert "Aspirin" in result["allergies"]

def test_allergic_drug_aspirin_with_bypass():
    """Test that the human-in-the-loop bypass triage parameter successfully overrides the allergy block."""
    from backend.agents.agent_system import analyze_ingredient
    result = analyze_ingredient("Aspirin", bypass_triage=True)
    
    assert result["status"] == "normal"
    assert "report" in result
    assert result["ingredient"] == "Aspirin"

def test_ai_pharmacist_chat():
    """Test that the follow-up AI Pharmacist Chat responds to questions based on report context."""
    from backend.agents.agent_system import answer_followup_question
    
    chat_response = MagicMock()
    chat_response.text = "You can take this with milk since there are no calcium binding conflicts."
    mock_client_instance.models.generate_content.return_value = chat_response
    
    reply = answer_followup_question(
        ingredient="Acetaminophen",
        report="This is a mock report context.",
        question="Can I take this with milk?",
        lang="en"
    )
    
    assert "milk" in reply.lower() or "calcium" in reply.lower()
