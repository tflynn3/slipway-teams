.PHONY: validate

validate:
	@python3 scripts/validate.py
	@python3 -m py_compile bridges/codex-mcp/server.py bridges/pr-agent-mcp/server.py scripts/validate.py
	@bash -n scripts/render-team.sh
	@echo "All validations passed."
