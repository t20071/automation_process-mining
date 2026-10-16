"""
Agent layer — the LLM may only *propose*; the gate decides.

llm_client    ActionProposal schema plus Groq and deterministic providers
gate_engine   Confidence / policy / high-impact gates with an append-only audit log
"""
