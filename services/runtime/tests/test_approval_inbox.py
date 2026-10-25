from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from conftest import TOKEN
from test_approvals import approved_gateway
from test_tool_registry import scope
from veya.api.app import create_app
from veya.config import Settings
from veya.policy.inbox import ApprovalInbox

REVIEWER='fixture-reviewer-credential-separate-00001'


def inbox_fixture(tmp_path):
    executor, actor, proposal, policies, _, calls, now, store, _, _ = approved_gateway(tmp_path)
    inbox=ApprovalInbox(executor, actor, scope())
    item=inbox.enqueue('inbox_write', proposal.id, expires_at=1090)
    settings=Settings('test','http://127.0.0.1:4318',tmp_path,actor.tenant_id,'env:VEYA_TEST_TOKEN')
    app=create_app(settings,TOKEN,approval_inbox=inbox,reviewer_token=REVIEWER)
    return app,inbox,item,executor,actor,proposal,policies,calls,now


def test_reviewer_lists_exact_proposal_and_competing_decisions_conflict(tmp_path):
    app,inbox,item,executor,actor,proposal,_,calls,_=inbox_fixture(tmp_path)
    headers={'Authorization':'Bearer '+TOKEN,'X-Veya-Reviewer-Token':REVIEWER}
    with TestClient(app,headers=headers) as client:
        page=client.get('/v1/approvals').json()
        assert page['items'][0]['id']==item['id']
        detail=client.get('/v1/approvals/'+item['id']).json()
        assert detail['arguments']=={'invoice_id':'inv'}
        assert detail['policy_version']=='policy_1'
        def decide(decision):
            return client.post('/v1/approvals/'+item['id']+'/decision',json={
                'revision':1,'decision':decision,'note':'Reviewed invoice evidence'})
        with ThreadPoolExecutor(2) as pool:
            replies=list(pool.map(decide,['approve','reject']))
        assert sorted(r.status_code for r in replies)==[200,409]
        assert calls==[]  # Review is not dispatch.
        assert client.get('/v1/approvals').json()['items']==[]
        assert client.get('/v1/approvals/'+item['id']).json()['revision']==2


def test_runtime_token_alone_cannot_review_and_expired_request_conflicts(tmp_path):
    app,_,item,_,_,_,_,calls,now=inbox_fixture(tmp_path)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
        assert client.get('/v1/approvals').status_code==403
        client.headers['X-Veya-Reviewer-Token']=REVIEWER
        now[0]=1091
        response=client.post('/v1/approvals/'+item['id']+'/decision',json={'revision':1,'decision':'approve','note':'Reviewed'})
        assert response.status_code==409
        assert calls==[]


def test_expired_review_can_be_replaced_without_changing_operation_identity(tmp_path):
    _,inbox,item,_,_,proposal,_,calls,now=inbox_fixture(tmp_path)
    now[0]=1091
    renewed=inbox.enqueue('inbox_write',proposal.id,expires_at=1150)
    assert renewed['id']!=item['id']
    assert renewed['operation_key']==item['operation_key']
    assert inbox.get(item['id'])['state']=='superseded'
    from veya.domain.models import DomainError
    import pytest
    with pytest.raises(DomainError):
        inbox.decide(item['id'],1,'approve','Old view')
    assert inbox.decide(renewed['id'],1,'approve','Fresh review')['state']=='approved'
    assert calls==[]


def test_approved_inbox_receipt_executes_once_through_gateway_and_pages_are_bounded(tmp_path):
    import asyncio
    app,inbox,item,executor,actor,proposal,_,calls,_=inbox_fixture(tmp_path)
    for i in range(3): inbox.enqueue('page_'+str(i),proposal.id,expires_at=1090)
    with TestClient(app,headers={'Authorization':'Bearer '+TOKEN,'X-Veya-Reviewer-Token':REVIEWER}) as client:
        first=client.get('/v1/approvals?limit=2').json()
        second=client.get('/v1/approvals',params={'limit':2,'after':first['next_cursor']}).json()
        assert len({i['id'] for i in first['items']+second['items']})==4
        assert client.get('/v1/approvals?limit=101').status_code==422
        result=client.post('/v1/approvals/'+item['id']+'/decision',json={'revision':1,'decision':'approve','note':'Reviewed'}).json()
        assert calls==[]
        for _ in range(2):
            assert asyncio.run(executor.execute(actor,scope(),'inbox_write',proposal.id,approval_id=result['receipt_id'])).state=='succeeded'
        assert len(calls)==1


def test_scope_cannot_list_another_reviewers_requests(tmp_path):
    from dataclasses import replace
    _,inbox,item,executor,actor,_,_,_,_=inbox_fixture(tmp_path)
    other=ApprovalInbox(executor,replace(actor,id='other_reviewer'),scope())
    assert other.pending()['items']==[]
    import pytest
    from veya.domain.models import DomainError
    with pytest.raises(DomainError): other.get(item['id'])
