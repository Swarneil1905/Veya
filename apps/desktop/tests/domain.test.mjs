import test from 'node:test';
import assert from 'node:assert/strict';
import {decideApproval, promotionGate, replayScenario, summarizeRuns} from '../src/domain.mjs';

test('an approval is recorded once and requires an audit note',()=>{
 const run={id:'r1',status:'Review',version:1};
 assert.throws(()=>decideApproval(run,'approve','  '),/reason/);
 const done=decideApproval(run,'approve','Receipt checked');
 assert.equal(done.status,'Completed');assert.equal(done.version,2);assert.equal(run.status,'Review');
 assert.throws(()=>decideApproval(done,'approve','retry'),/no longer/);
});
test('rejection stops the workflow and invalid decisions fail',()=>{
 assert.equal(decideApproval({status:'Review',version:1},'reject','Insufficient evidence').status,'Stopped');
 assert.throws(()=>decideApproval({status:'Review',version:1},'skip','note'),/Unknown/);
});
for (const fault of ['stale-policy','tool-timeout','injection','missing-receipt']){
 test(`${fault}: baseline failure and candidate fixture stay isolated`,()=>{
   const baseline=replayScenario({fault,repaired:false});const candidate=replayScenario({fault,repaired:true});
   assert.equal(baseline.passed,false);assert.equal(candidate.passed,true);
   assert.equal(candidate.externalActions,0);assert.equal(candidate.modelCalled,false);
   assert.notEqual(baseline.outcome,candidate.outcome);
 });
}
test('synthetic reports cannot bypass release gates',()=>{
 assert.equal(promotionGate({source:'synthetic-demo',tasks:10000,lowerBoundUplift:10,policyViolations:0,p95LatencySeconds:1}).allowed,false);
});
test('real release evidence must satisfy every gate',()=>{
 assert.equal(promotionGate({source:'live-evaluation'}).allowed,false);
 const report={source:'live-evaluation',tasks:200,lowerBoundUplift:0.01,policyViolations:0,leakageDetected:false,p95LatencySeconds:44};
 assert.equal(promotionGate(report).allowed,true);
 for(const patch of [{tasks:199},{lowerBoundUplift:0},{lowerBoundUplift:NaN},{policyViolations:1},{leakageDetected:true},{p95LatencySeconds:46},{p95LatencySeconds:undefined}])assert.equal(promotionGate({...report,...patch}).allowed,false);
});
test('queue totals follow decisions',()=>{
 const runs=[{status:'Review',version:1},{status:'Failed'},{status:'Completed'}];
 assert.deepEqual(summarizeRuns(runs),{total:3,completed:1,review:1,failed:1});
 assert.equal(summarizeRuns([decideApproval(runs[0],'approve','Reviewed'),...runs.slice(1)]).review,0);
});
