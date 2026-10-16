# AI integration decisions

The implementation was checked against the installed, locked SDKs and these primary references on 16 October 2026:

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs): native JSON Schema with strict output. Schema adherence is separate from factual correctness.
- [GPT-4.1 mini model capabilities](https://developers.openai.com/api/docs/models/gpt-4.1-mini): an example model supporting structured outputs. Access remains account-dependent; the application requires explicit `OPENAI_MODEL` for live mode.
- [LangChain ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai): `with_structured_output(Extraction, method="json_schema", strict=True, include_raw=True)` supplies the Pydantic schema and exposes usage.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts): `interrupt()` persists the pause; `Command(resume=...)` resumes the same server-owned thread. Interrupted nodes restart, which is why the pause node has no side effects before interrupt.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence): PostgreSQL checkpoint initialization uses `PostgresSaver.from_conn_string(...)` as a context manager and explicit `setup()`.

The live provider uses ChatOpenAI, not canned responses. The paid transport was not exercised without an authorized API key. `test_live_adapter.py` exercises the actual installed LangChain/OpenAI structured request and parsing path against an HTTP mock, asserting the model ID, strict schema and token usage. Other automated workflow tests inject deterministic providers. Provider retries belong to the service; SDK retry count is zero.

For the separate **paid** smoke test, from `backend/`, first set a test database URL, `OPENAI_MODEL`, `OPENAI_API_KEY` and `RUN_LIVE_AI=1`, then run:

```text
uv run pytest tests/test_live.py -m live -v
```

The smoke test sends only a synthetic kitchen-sink report. Ordinary CI never sets RUN_LIVE_AI. End-to-end behavior works offline.

All extraction fields are required in the schema; unsupported facts use nullable values or empty lists. Every evidence reference must identify a message in the authorized snapshot and use an exact source substring. Rejected quotations are never replaced with invented text. Category inference, summary fidelity, contradiction handling and question relevance still need semantic evaluation and human review.

Model invocations record nullable usage/cost, including every transport attempt. Pricing is supplied by backend configuration for the explicitly chosen model. No prices are assumed, and latency is not a quality score. The prompt treats all tenant text as untrusted data, never ownership or approval instructions. There are no external tools available to the model.
