import json
import unittest
from incidentlab.kubernetes_experiment import FaultControl


class FakeCli:
    def __init__(self):self.commands=[];self.fail_apply=False;self.owner='incidentlab-testbed'
    def verify_scope(self):pass
    def run(self,*args):
        self.commands.append(args)
        if args[0]=='get':return json.dumps({'metadata':{'labels':{'app.kubernetes.io/part-of':self.owner}},'spec':{'replicas':1}})
        if self.fail_apply and args[0]=='scale' and args[-1]=='--replicas=0':raise RuntimeError('partial command failure')
        return ''


class FaultTests(unittest.TestCase):
    def test_partial_apply_still_restores(self):
        cli=FakeCli();cli.fail_apply=True;control=FaultControl(cli,'inventory','unavailable')
        with self.assertRaises(RuntimeError):control.apply()
        self.assertTrue(control.active)
        control.restore()
        self.assertIn(('scale','deployment/inventory','--replicas=1'),cli.commands)
        self.assertFalse(control.active)

    def test_ownership_failure_prevents_mutation(self):
        cli=FakeCli();cli.owner='other';control=FaultControl(cli,'inventory','delay')
        with self.assertRaises(ValueError):control.apply()
        self.assertFalse(control.active)
        self.assertFalse(any(c[0] in ('exec','scale') for c in cli.commands))

    def test_changed_ownership_prevents_restoration_to_other_app(self):
        cli=FakeCli();control=FaultControl(cli,'inventory','delay');control.apply();cli.owner='other'
        before=len(cli.commands)
        with self.assertRaises(ValueError):control.restore()
        self.assertFalse(any(c[0] in ('exec','scale') for c in cli.commands[before:]))


if __name__=='__main__':unittest.main()
