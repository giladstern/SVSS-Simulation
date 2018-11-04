from enum import Enum


class Stage(Enum):
    MW_VALUES = 1
    MW_ACK = 2
    MW_CORROBORATE = 3
    MW_L = 4
    MW_M = 5
    MW_OK = 6
    MW_REC = 7
    SVSS_VALUES = 8
    SVSS_G = 9

    def __lt__(self, other):
        return self.value < other.value

    def __gt__(self, other):
        return self.value > other.value

    def __le__(self, other):
        return self.value <= other.value

    def __ge__(self, other):
        return self.value >= other.value


class Message:
    def __init__(self, content, tag, sender, stage, moderator=None, RB=False):
        self.content = content
        self.sender = sender
        self.stage = stage
        self.moderator = moderator
        self.RB = RB
        self.tag = tag

    def __repr__(self):
        return str(self.content) + ", " + str(self.tag)

    def __str__(self):
        return self.__repr__()
