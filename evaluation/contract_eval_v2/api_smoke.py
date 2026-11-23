"""One real API smoke case on isolated DB; separate from benchmark scores."""
import io
import os
import secrets
import time
import uuid

from docx import Document
from fastapi.testclient import TestClient

from evaluation.contract_eval_v2.full_audit import OUT, read_rows, write_json
from evaluation.contract_eval_v2.full_run import check


def main():
    check()
    assert os.environ.get('CONTRACTLENS_EVAL_ISOLATED') == '1'
    from app.core.settings import get_settings
    from app.main import app
    assert get_settings().llm_provider == 'groq'
    source = next(r for r in read_rows(OUT / 'inputs.jsonl') if r['id'] == 'OT-01-T1')
    doc = Document()
    for line in (OUT / source['contract_path']).read_text(encoding='utf-8').splitlines():
        doc.add_paragraph(line)
    data = io.BytesIO();doc.save(data)
    password = secrets.token_urlsafe(32)
    email = f'full-smoke-{uuid.uuid4().hex}@example.com'
    proof = {'scope': 'one_actual_API_case_not_part_of_369_QA_or_117_workflows',
             'authentication_overridden': False, 'LLM_stubbed': False, 'steps': {}}
    started = time.perf_counter()
    def expect(name, response, expected=200):
        proof['steps'][name] = response.status_code
        write_json(OUT / 'API_SMOKE.json', proof)
        assert response.status_code == expected, (name, response.status_code)
        print(name, response.status_code, flush=True)
        return response
    with TestClient(app) as client:
        expect('register', client.post('/api/v1/auth/register', json={'email': email, 'password': password}))
        login = expect('login', client.post('/api/v1/auth/login', json={'email': email, 'password': password})).json()
        headers = {'Authorization': 'Bearer ' + login['access_token']}
        upload = expect('upload_docx', client.post('/api/v1/upload', headers=headers,
            files={'file': ('full-smoke.docx', data.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})).json()
        cid = upload['contract_id'];proof['contract_id'] = cid
        assert upload['chunk_count'] > 0
        analysis = expect('analyze', client.post('/api/v1/analyze', headers=headers,
            json={'contract_id': cid})).json()
        assert analysis['analysis']['clauses'] and isinstance(analysis['risks'], list)
        chat = expect('chat', client.post('/api/v1/chat', headers=headers,
            json={'contract_id': cid, 'question': 'Điều 2 của hợp đồng có trái pháp luật không?'})).json()
        assert chat['answer'] and chat['contract_id'] == cid
        history = expect('persisted_history', client.get(f'/api/v1/chat/{cid}/history', headers=headers)).json()
        proof['history_messages'] = len(history['messages'])
        # History entries are question/answer pairs, not individual LangChain messages.
        assert len(history['messages']) == 1
        assert history['messages'][0]['question'] == 'Điều 2 của hợp đồng có trái pháp luật không?'
        assert history['messages'][0]['answer'] == chat['answer']
        report = expect('persisted_report', client.get(f'/api/v1/contracts/{cid}/report', headers=headers))
        assert report.json()
        expect('unauthenticated_report_denied', client.get(f'/api/v1/contracts/{cid}/report'), 401)
    proof.update(status='passed', seconds=round(time.perf_counter()-started, 2))
    write_json(OUT / 'API_SMOKE.json', proof)


if __name__ == '__main__':
    main()
