import unittest

from scripts.evaluate_incident_groups import evaluate,group


def windows(flags):
    return [dict(start=10+3*i,end=13+3*i,operational_alert=flag,
                 candidates=[dict(service='checkout')]) for i,flag in enumerate(flags)]


class IncidentGroupingChecks(unittest.TestCase):
    def test_single_warning_does_not_create_incident(self):
        self.assertEqual(group(windows([False,True,False,False])),[])

    def test_consecutive_warnings_and_recovery_form_one_episode(self):
        episodes=group(windows([False,True,True,True,False,False]))
        self.assertEqual(len(episodes),1)
        self.assertEqual(episodes[0]['opened_at'],19)
        self.assertEqual(episodes[0]['closed_at'],28)

    def test_evaluation_schedule_does_not_change_grouping_decisions(self):
        values=windows([False,True,True,True,False,False])
        fault=evaluate(values,dict(phase='test',target='checkout',onset=14,recovery=22))
        healthy=evaluate(values,dict(phase='test',target=None,onset=None,recovery=None))
        self.assertEqual(fault['episodes'],healthy['episodes'])
        self.assertTrue(fault['fault_incident_detected'])
        self.assertEqual(healthy['healthy_false_incidents'],1)


if __name__=='__main__':unittest.main()
