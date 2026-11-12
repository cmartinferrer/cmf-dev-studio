"""Single repository orchestrator: plan, develop, review, verify and repair.
WorkspaceService owns snapshots, authorization and persistence; agents own prompts.
"""
from __future__ import annotations
import re
from cmf_dev_studio.agents.analyst import AnalystAgent
from cmf_dev_studio.agents.developer import DeveloperAgent, build_workspace_prompt
from cmf_dev_studio.agents.tester import TesterAgent
from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.workflow import WorkflowPolicy

class Orchestrator:
    def __init__(self, llm, policy=None):
        self.policy = policy or WorkflowPolicy()
        self.analyst = AnalystAgent(llm)
        self.developer = DeveloperAgent(llm)
        self.tester = TesterAgent(llm)

    def plan_patch(self, *args, **kwargs):
        return self.analyst.plan_patch(*args, **kwargs)

    def generate_patch(self, *args, **kwargs):
        return self.developer.generate_patch(*args, max_attempts=self.policy.max_attempts, **kwargs)

    def review_patch(self, *args, **kwargs):
        return self.tester.review_patch(*args, **kwargs)

    def prepare(self, task, inventory, approved, languages, original, approved_paths, validate, stage, save_plan):
        """Run the initial analyst/developer/tester sequence."""
        stage("analyst")
        plan = self.plan_patch(task, inventory, approved, languages)
        save_plan(plan)
        prompt = build_workspace_prompt(task, inventory, approved, languages)
        return self.reviewed_patch(task, prompt, plan, original, approved_paths, validate, stage)

    def reviewed_patch(self, task, prompt, plan, original, approved_paths, validate, stage, feedback=''):
        """Coordinate bounded Developer/Tester review; storage is supplied by caller."""
        policy = self.policy
        for _ in range(policy.max_attempts):
            stage('developer_repair' if feedback else 'developer')
            operations = self.generate_patch(prompt, plan, feedback=feedback, validate=validate)
            stage('tester')
            issues = self.review_patch(task, plan, operations, original=original, approved_paths=approved_paths)
            if not issues:
                return operations
            feedback += '\nTester review: ' + '; '.join(issues)
        raise ValueError('Tester review unresolved: ' + '; '.join(issues))

    @staticmethod
    def repository_test_cycle(policy, run, repair):
        """Single owner of repository test/repair scheduling. Callbacks own I/O.

        run(attempt) returns (passed, output); repair(output) returns (retry, output).
        """
        for attempt in range(1, policy.max_attempts + 1):
            passed, output = run(attempt)
            if passed:
                return True, output
            recoverable = bool(re.match(r'^Runner: [^\n]+ \(exit [1-9][0-9]*; test_result\)', output))
            if not policy.can_retry(attempt, recoverable=recoverable):
                return False, output
            retry, output = repair(output)
            if not retry:
                return False, output
        raise AssertionError('Unreachable test cycle')
