"""
Report Generator Agents - Translation and Quality Loop for Latvian Output.

Architecture:
1. Aggregator generates first draft in English (with all context)
2. Translator converts to Latvian Markdown
3. LoopAgent validates translation quality against original draft
"""

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools import FunctionTool
from .base_config import MODEL_CONFIGS


def exit_report_loop():
    """Signal that report translation is approved and loop should exit."""
    return {
        "status": "approved",
        "message": "Latvian translation approved - quality validated"
    }


def create_translator_agent():
    """
    Create the Translator agent that converts English draft to Latvian.
    
    This agent:
    - Receives the English draft from aggregator
    - Translates to professional Latvian
    - Preserves ALL context and structure
    - Does NOT add or remove information
    
    Returns:
        LlmAgent: Configured translator agent
    """
    config = MODEL_CONFIGS.get("translator", MODEL_CONFIGS["report"])
    
    agent = LlmAgent(
        name="TranslatorAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        description="Translates English report draft to professional Latvian",
        instruction="""You are a professional translator specializing in legal Latvian.

You will receive:
- English draft: {+draft_report_en|No draft available+}

Your task:
Translate the entire report to Latvian while:
1. **Preserving Structure**: Keep the exact Markdown format
   - ## Kopsavilkums (Summary)
   - ## Izmaiņas pa Avotiem (Changes by Source)
   - ### Likumi.lv, ### TAP Portāls, ### Saeima

2. **Professional Latvian**: 
   - Use proper legal terminology
   - Formal, professional tone
   - Correct grammar and spelling
   
3. **Preserving ALL Content**:
   - Do NOT add information not in the English draft
   - Do NOT remove any items
   - Translate dates, titles, descriptions accurately
   - Keep URLs unchanged

4. **URL Formatting**:
   - Keep source URLs on separate lines
   - Format: `- [Source URL]`

Output ONLY the Latvian translation in Markdown format.""",
        output_key="draft_latvian_report",
    )
    
    return agent


def create_report_critic_agent():
    """
    Create the Critic agent that validates translation quality.
    
    This agent:
    - Compares Latvian translation against English original
    - Checks grammar, structure, and completeness
    - Responds "APSTIPRINĀTS" if perfect, otherwise provides feedback
    
    Returns:
        LlmAgent: Configured critic agent
    """
    config = MODEL_CONFIGS.get("critic", MODEL_CONFIGS["report"])
    
    agent = LlmAgent(
        name="ReportCriticAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        description="Validates Latvian translation quality against English original",
        instruction="""You are a quality control expert for Latvian legal translations.

You will receive:
- Original English draft: {+draft_report_en|No draft available+}
- Latvian translation: {+draft_latvian_report|No translation available+}

Your task:
Evaluate the Latvian translation against the English original:

1. **Completeness Check**:
   - All items from English draft are present in Latvian
   - No items added or removed
   - All URLs preserved

2. **Translation Accuracy**:
   - Latvian conveys same meaning as English
   - Legal terminology is correct
   - No mistranslations or omissions

3. **Grammar & Style**:
   - Professional Latvian grammar
   - Correct spelling
   - Formal tone appropriate for professional reports
   - Linguistic structures of native Latvian

4. **Structure Validation**:
   - Markdown format preserved (## Kopsavilkums, ### Likumi.lv, etc.)
   - URLs on separate lines
   - Consistent formatting

**Decision**:
- IF all checks pass perfectly, respond with EXACTLY: "APSTIPRINĀTS"
- OTHERWISE, provide 2-3 specific corrections needed

Be strict but fair. Minor style improvements are acceptable, but only flag significant issues.""",
        output_key="critique",
    )
    
    return agent


def create_report_refiner_agent():
    """
    Create the Refiner agent that improves translation based on critique.
    
    This agent:
    - Receives critique from critic
    - Either fixes issues OR calls exit_report_loop() if approved
    - Updates the Latvian translation
    
    Returns:
        LlmAgent: Configured refiner agent
    """
    config = MODEL_CONFIGS.get("refiner", MODEL_CONFIGS["report"])
    
    agent = LlmAgent(
        name="ReportRefinerAgent",
        model=Gemini(
            model=config["model"],
            retry_options=config["retry_options"]
        ),
        description="Refines Latvian translation based on critique or exits loop if approved",
        instruction="""You are a translation refiner for Latvian legal reports.

You will receive:
- Original English draft: {+draft_report_en|No draft available+}
- Current Latvian translation: {+draft_latvian_report|No translation available+}
- Critique: {+critique|No critique available+}

Your task:
1. **Check if approved**: 
   - IF critique is EXACTLY "APSTIPRINĀTS", call the exit_report_loop() function immediately
   - Do NOT make any changes, just exit

2. **Otherwise, refine the translation**:
   - Address ALL points in the critique
   - Compare against English original for accuracy
   - Preserve ALL content (do not add/remove items)
   - Fix grammar, translation errors, formatting issues
   
3. **Output**:
   - Return the improved Latvian report in Markdown format
   - Ensure all critique points are resolved

IMPORTANT: Only call exit_report_loop() if critique is exactly "APSTIPRINĀTS" with no other text.""",
        tools=[FunctionTool(exit_report_loop)],
        output_key="draft_latvian_report",  # Overwrites with improved version
    )
    
    return agent


def create_report_agent():
    """
    Create the full Report Generator pipeline with quality loop.
    
    Architecture:
    1. Translator: English → Latvian (first draft, outputs to draft_latvian_report)
    2. LoopAgent (max 3 iterations):
       - Critic: Validates quality against English original
       - Refiner: Fixes issues OR exits if "APSTIPRINĀTS"
    
    The final Latvian report is stored in session state as 'draft_latvian_report'.
    The Refiner's output is the last agent output, which SSE streams to frontend.
    
    Returns:
        SequentialAgent: Complete report generation pipeline
    """
    translator = create_translator_agent()
    critic = create_report_critic_agent()
    refiner = create_report_refiner_agent()
    
    # Quality validation loop
    quality_loop = LoopAgent(
        name="ReportQualityLoop",
        sub_agents=[critic, refiner],
        max_iterations=4,  # Prevent runaway costs
    )
    
    # Full pipeline: Translate → Validate
    # Refiner is the last agent, its output_key="draft_latvian_report" will be in SSE
    report_pipeline = SequentialAgent(
        name="ReportGenerator",
        sub_agents=[translator, quality_loop],
    )
    
    return report_pipeline