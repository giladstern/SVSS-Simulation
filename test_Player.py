from Player import Player
from Message import *
from Polynomial import *
from random import randrange
from Simulator import RandomOrderSimulator
from Simulator import Simulator as RBRandomOrderSimulator


class FakeSimulator:
    def __init__(self):
        self.messages = []
        self.RB_list = []

    def send(self, message, to):
        self.messages.append((message, to))

    def RB(self, message):
        self.RB_list.append(message)

    def time(self):
        return 0


class MWRandomOrderSimulator(RandomOrderSimulator):
    def __init__(self):
        super().__init__()
        self.reconstruct_started = {}

    def send(self, message, to):
        if message.stage <= Stage.MW_REC:
            self.waiting.append((message, to))

    def RB(self, message):
        if message.stage <= Stage.MW_REC:
            self.waiting.append((message,None))

    def step(self):
        message, to = self.waiting.pop(randrange(len(self.waiting)))
        tag = message.tag

        if to:
            self.players[to].DMM(message)
        else:
            for player in self.players.values():
                player.DMM(message)

        if tag not in self.reconstruct_started:
            self.reconstruct_started[tag] = []

        for player in self.players.values():
            if tag in player.MW_share_done and player.id not in self.reconstruct_started[tag]:
                player.MW_reconstruct(tag)
                self.reconstruct_started[tag].append(player.id)
        self.inner_time += 1


class MWEvilRandomOrderSimulator(MWRandomOrderSimulator):
    def __init__(self):
        super().__init__()
        self.dropped = None

    def RB(self, message):
        if message.stage == Stage.MW_REC and not self.dropped:
            self.dropped = message
            return
        super().RB(message)

    def release_delayed(self):
        if self.dropped:
            self.RB(self.dropped)


class EvilPlayer(Player):
    def __init__(self, simulator, id, n, t):
        super().__init__(simulator, id, n, t)

    def RB(self, message):
        if message.stage == Stage.MW_REC:
            message.content = (message.content[0], message.content[1] + 1)
        super().RB(message)

def test_polynomials():
    ### Univariate polynomial tests ###
    f = Polynomial([1, 2, 3])
    g = Polynomial([0, -1, 1])

    # Check minimize
    assert Polynomial([1, 2, 0]) == Polynomial([1, 2])
    assert Polynomial([1, 2, 0]).deg == Polynomial([1, 2]).deg
    assert Polynomial([0]).coef == [0]

    # Check basic operations
    assert f + g == Polynomial([1, 1, 4])
    assert f * g == Polynomial([0, -1, -1, -1, 3])
    assert f.eval(2) == 17
    f.cmult(2)
    assert f == Polynomial([2, 4, 6])

    # Check interpolation
    p = Polynomial.interpolate([(1, 5), (2, 11), (3, 19), (4, 29)])
    assert p.eval(0) == 1

    p = Polynomial([3, -15, 6])
    q = Polynomial.interpolate([(x, p.eval(x)) for x in range(20)])
    assert p == q

    ### Bivariate polynomial tests ###
    f = BivariatePolynomial([[1, -1, 2], [3, 0, 2], [-1, -2, 1]])
    g = BivariatePolynomial([[2, 0], [1, 2, 3], [0]])

    # Check Minimize
    assert g == BivariatePolynomial([[2], [1, 2, 3]])

    # Check Basic Operations
    assert f + g == BivariatePolynomial([[3, -1, 2], [4, 2, 5], [-1, -2, 1]])
    assert f * g == BivariatePolynomial([[2, -2, 4], [7, 1, 7, 1, 6], [1, 2, 13, 4, 6], [-1, -4, -6, -4, 3]])
    g.cmult(0.5)
    assert g == BivariatePolynomial([[1.0], [0.5, 1.0, 1.5]])

    f_lam = lambda x, y: x ** 2 * y ** 2 - 2 * x ** 2 * y - x ** 2 + 2 * x * y ** 2 + 3 * x + 2 * y ** 2 - y + 1

    # Check bivariate evaluation
    assert f.eval(2, 3) == f_lam(2, 3)
    assert f.eval(0, 4) == f_lam(0, 4)
    assert f.eval(-2, 5) == f_lam(-2, 5)

    assert f.g(2) == Polynomial.interpolate([(i,f.eval(2,i)) for i in range(3)])
    assert f.h(2) == Polynomial.interpolate([(i,f.eval(i,2)) for i in range(3)])

def test_random_polynomials():
    for i in range(10):
        secret = randint(1, 100)
        deg = 4
        assert Polynomial.random_polynomial(secret, deg, 16).eval(0) == secret, "Univariate polynomial with wrong secret"
        bp = BivariatePolynomial.random_polynomial(secret, deg, 100)
        assert bp.eval(0,0) == secret, "Bivariate polynomial with wrong secret"

        j = randint(1,4)
        assert bp.g(j) == Polynomial.interpolate([(i,bp.eval(j,i)) for i in range(deg + 1)])
        assert bp.h(j) == Polynomial.interpolate([(i, bp.eval(i,j)) for i in range(deg + 1)])


def test_mw_deal():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)

    p.deal_MW(1, 1, 1, 1)
    p.MW_moderate(1, 1, 1, 1)
    assert len(sim.messages) == 5, "Wrong number of messages"


def test_receive_mw_values():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)

    p.deal_MW(1, 1, 1, 2)
    tag = (1, 1, 1, 2)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES and to == p.id:
            p.DMM(message)

    assert len(p.MW_data) == 1, "Data not registered"
    assert len(p.MW_data[tag]) == 2, "Not enough values in MW_data"
    assert tag in p.DEAL, "Didn't create DEAL"
    assert tag in p.MW_corroborate, "Didn't create corroborate"
    assert tag in p.MW_ack, "Didn't create ack"


def test_receive_mw_values_mod():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)

    p.deal_MW(1, 1, 1, 1)
    p.MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    messages = sim.messages[:]
    for message, to in messages:
        if message.stage == Stage.MW_VALUES and to == p.id:
            p.DMM(message)

    assert tag in p.MW_mod_data, "Mod data not registered"
    assert len(p.MW_data) == 1, "Data not registered"
    assert len(p.MW_data[tag]) == 2, "Not enough values in MW_data"
    assert tag in p.DEAL, "Didn't create DEAL"
    assert tag in p.MW_corroborate, "Didn't create corroborate"
    assert tag in p.MW_ack, "Didn't create ack"


def test_receive_mw_corroborate():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)

    p.deal_MW(1, 1, 1, 2)
    tag = (1, 1, 1, 2)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES and to == p.id:
            p.DMM(message)

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE and to == p.id:
            p.DMM(message)

    assert tag in p.MW_corroborate, "Didn't create corroborate"
    assert 1 in p.MW_corroborate[tag], "Didn't add self"
    assert len(p.MW_corroborate[tag]) == 1, "Added wrong number"


def test_receive_mw_ack():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)

    p.deal_MW(1, 1, 2, 1)
    tag = (1, 2, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES and to == p.id:
            p.DMM(message)

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE and to == p.id:
            p.DMM(message)

    for RB in sim.RB_list:
        p.DMM(RB)

    assert tag in p.MW_ack, "Didn't initialize ack"
    assert 1 in p.MW_ack[tag], "Didn't add ack to list"
    assert 1 in p.DEAL[tag], "Didn't add player to DEAL"


def test_weird_order_mw_corroborate():
    sim = FakeSimulator()
    p = Player(sim, 1, 4, 1)
    q = Player(sim, 2, 4, 1)

    p.deal_MW(1, 1, 1, 2)
    tag = (1, 1, 1, 2)

    # p messages
    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES and to == p.id:
            p.DMM(message)

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE and to == p.id:
            p.DMM(message)

    for RB in sim.RB_list:
        p.DMM(RB)

    # q messages
    for RB in sim.RB_list:
        q.DMM(RB)

    assert tag in q.MW_ack, "Didn't save ack"
    assert 1 in q.MW_ack[tag], "Didn't add to acks"

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE and to == q.id:
            q.DMM(message)

    assert tag in q.MW_corroborate, "Didn't add to corr"
    assert len(q.MW_corroborate[tag]), "Wrong number in corr"

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES and to == q.id:
            q.DMM(message)

    assert tag in q.DEAL, "Didn't initialize deal"
    assert 1 in q.DEAL[tag], "Didn't add to DEAL"
    assert len(q.MW_corroborate[tag]) == 0, "Didn't remove from corr"


def test_MW_L():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    players[1].deal_MW(1, 1, 1, 1)
    players[1].MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    mod = players[1]
    assert tag in mod.MW_mod_data, "Didn't initialize data"
    assert tag in mod.MW_corroborate, "Didn't initialize corroborate"
    assert not mod.MW_corroborate[tag], "Corroborate not empty"
    assert tag in mod.MW_mod_M, "Didn't initialize M"

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    assert len(mod.MW_corroborate[tag]) == 4, "Wrong amount of data in corroborate"

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    assert mod.MW_ack[tag], "Wrong ack"
    assert len(mod.MW_ack[tag]) == 4, "Wrong number of acks"
    assert len(mod.MW_L[tag]) == 4, "Wrong L"
    assert len(mod.MW_mod_M[tag]) == 3, "Wrong size M"
    assert len(mod.MW_corroborate[tag]) == 1, "Didn't reduce"

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            break
    else:
        assert False, "No M set sent"


def test_MW_L_weird():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    players[1].deal_MW(1, 1, 1, 1)
    players[1].MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    mod = players[1]
    assert tag in mod.MW_mod_data, "Didn't initialize data"
    assert tag in mod.MW_corroborate, "Didn't initialize corroborate"
    assert not mod.MW_corroborate[tag], "Corroborate not empty"
    assert tag in mod.MW_mod_M, "Didn't initialize M"

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    assert len(mod.MW_corroborate[tag]) == 4, "Wrong amount of data in corroborate"

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                if i !=1:
                    players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            mod.DMM(RB)

    assert mod.MW_ack[tag], "Wrong ack"
    assert len(mod.MW_ack[tag]) == 4, "Wrong number of acks"
    assert len(mod.MW_L[tag]) == 3, "Wrong L"
    assert len(mod.MW_mod_M[tag]) == 3, "Wrong size M"
    assert len(mod.MW_corroborate[tag]) == 1, "Didn't reduce"

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            break
    else:
        assert False, "No M set sent"


def test_MW_dealer_OK():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    players[1].deal_MW(1, 1, 1, 1)
    players[1].MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    mod = players[1]

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_OK:
            break
    else:
        assert False, "No OK sent"


def test_MW_dealer_weird_OK():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    players[1].deal_MW(1, 1, 1, 2)
    tag = (1, 1, 1, 2)

    mod = players[2]
    mod.MW_moderate(1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                if i != 1:
                    players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                if i != 1:
                    players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            for i in players:
                if i != 1:
                    players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            players[1].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            players[1].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            players[1].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_OK:
            break
    else:
        assert False, "No OK sent"

def test_MW_dealer_OK():
    sim = FakeSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}

    players[1].deal_MW(1, 1, 1, 1)
    players[1].MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    mod = players[1]

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_OK:
            break
    else:
        assert False, "No OK sent"


def test_MW_finish():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    players[1].deal_MW(1, 1, 1, 1)
    players[1].MW_moderate(1, 1, 1, 1)
    tag = (1, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    mod = players[1]

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_OK:
            for i in players:
                players[i].DMM(RB)

    assert tag in mod.MW_share_done, "Didn't finish"

def test_MW_rec():
    sim = FakeSimulator()
    players = {i:Player(sim, i, 4, 1) for i in range(1, 4+1)}

    secret = randint(1, 40)

    players[1].deal_MW(secret, 1, 1, 1)
    tag = (1, 1, 1, 1)
    SVSS_tag = (tag[0], tag[1])
    mod = players[1]
    mod.MW_moderate(secret, 1, 1, 1)

    for message, to in sim.messages:
        if message.stage == Stage.MW_VALUES:
            players[to].DMM(message)

    for message, to in sim.messages:
        if message.stage == Stage.MW_CORROBORATE:
            players[to].DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_ACK:
            for i in players:
                players[i].DMM(RB)

    for message, to in sim.messages:
        if message.stage == Stage.MW_L:
            mod.DMM(message)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_L:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_M:
            for i in players:
                players[i].DMM(RB)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_OK:
            for i in players:
                players[i].DMM(RB)

    for player in players.values():
        player.MW_reconstruct(tag)

    for RB in sim.RB_list:
        if RB.stage == Stage.MW_REC:
            for i in players:
                players[i].DMM(RB)

    for i in players:
        if players[i].MW_val[SVSS_tag][1][mod.id] != secret:
            assert False, "Wrong value"


def test_random_order_MW_run():
    sim = MWRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (1, 1, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 1, 1, mod)
    players[mod].MW_moderate(secret, 1, 1, dealer.id)

    while sim.remaining():
        sim.step()

    for player in players.values():
        assert SVSS_tag in player.MW_val and dealer.id in player.MW_val[SVSS_tag] and \
               mod in player.MW_val[SVSS_tag][dealer.id], "No value reconstructed"
        assert player.MW_val[SVSS_tag][dealer.id][mod] == secret, "Wrong secret"
        assert not player.DEAL, "DEAL not empty"
        assert not player.ACK, "ACK not empty"
        assert not player.D, "D not empty"


def test_leaving_in_deal():
    sim = MWEvilRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (1, 1, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 1, 1, mod)
    players[mod].MW_moderate(secret, 1, 1, dealer.id)

    while sim.remaining():
        sim.step()

    for player in players.values():
        assert SVSS_tag in player.MW_val and dealer.id in player.MW_val[SVSS_tag] and \
               mod in player.MW_val[SVSS_tag][dealer.id], "No value reconstructed"
        assert player.MW_val[SVSS_tag][dealer.id][mod] == secret, "Wrong secret"
        assert not player.D, "D not empty"
        assert player.invocations[tag][1], "Didn't update timeline"

    assert any(player.DEAL for player in players.values()), "DEAL empty for everybody"
    assert any(player.ACK for player in players.values()), "ACK empty for everybody"


def test_many_randomized_trials():
    for i in range(100):
        test_MW_rec()
        test_random_order_MW_run()
        test_leaving_in_deal()
        test_mw_evil_player()
        test_MW_delay()
        test_SVSS()
        test_SVSS_correct_RB()
        test_SVSS_evil_player()


def test_mw_evil_player():
    sim = MWRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 3 + 1)}
    evil_player = EvilPlayer(sim, 4, 4, 1)
    players[4] = evil_player
    sim.players = players

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (1, 1, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 1, 1, mod)
    players[mod].MW_moderate(secret, 1, 1, dealer.id)

    while sim.remaining():
        sim.step()

    used_evil_player = any(evil_player.id in players[1].MW_L[tag][i] for i in players[1].MW_M[tag])

    if not used_evil_player:
        for player in players.values():
            assert SVSS_tag in player.MW_val and dealer.id in player.MW_val[SVSS_tag] and \
                   mod in player.MW_val[SVSS_tag][dealer.id], "No value reconstructed"
            assert player.MW_val[SVSS_tag][dealer.id][mod] == secret, "Wrong secret"
            assert not player.DEAL, "DEAL not empty"
            assert not player.ACK, "ACK not empty"
            assert not player.D, "D not empty"
            assert player.invocations[tag][1], "Timeline not updated"

    else:
        for player in players.values():
            if player.id in player.MW_M and tag in player.MW_L and evil_player.id in player.MW_L[tag]:
                assert evil_player.id in player.D, "Liar not added to D"


def test_MW_sevreal_runs():
    sim = MWRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players
    runs = 5

    def helper(i):
        dealer = players[randint(1, 4)]
        mod = randint(1, 4)
        secret = randint(1, 40)
        tag = (i, 1, dealer.id, mod)
        SVSS_tag = (tag[0], tag[1])

        dealer.deal_MW(secret, i, 1, mod)
        players[mod].MW_moderate(secret, i, 1, dealer.id)
        return dealer, mod, secret, tag, SVSS_tag

    dealer = []
    mod = []
    secret = []
    tag = []
    SVSS_tag = []

    for i in range(1,2 * runs+1, 2):
        data = helper(i)

        dealer.append(data[0])
        mod.append(data[1])
        secret.append(data[2])
        tag.append(data[3])
        SVSS_tag.append(data[4])

    while sim.remaining():
        sim.step()

    for player in players.values():
        for i in range(runs):
            assert SVSS_tag[i] in player.MW_val and dealer[i].id in player.MW_val[SVSS_tag[i]] and \
                   mod[i] in player.MW_val[SVSS_tag[i]][dealer[i].id], "No value reconstructed"
            assert player.MW_val[SVSS_tag[i]][dealer[i].id][mod[i]] == secret[i], "Wrong secret"
            assert not player.DEAL, "DEAL not empty"
            assert not player.ACK, "ACK not empty"
            assert not player.D, "D not empty"


def test_MW_delay():
    sim = MWEvilRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (1, 1, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 1, 1, mod)
    players[mod].MW_moderate(secret, 1, 1, dealer.id)

    while sim.remaining():
        sim.step()

    for player in players.values():
        assert SVSS_tag in player.MW_val and dealer.id in player.MW_val[SVSS_tag] and \
               mod in player.MW_val[SVSS_tag][dealer.id], "No value reconstructed"
        assert player.MW_val[SVSS_tag][dealer.id][mod] == secret, "Wrong secret"
        assert not player.D, "D not empty"
        assert player.invocations[tag][1], "Didn't update timeline"

    assert any(player.DEAL for player in players.values()), "DEAL empty for everybody"
    assert any(player.ACK for player in players.values()), "ACK empty for everybody"

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (2, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 2, 1, mod)
    players[mod].MW_moderate(secret, 2, 1, dealer.id)

    while sim.remaining():
        sim.step()

    for player in players.values():
        if player.waiting:
            assert player.DEAL or player.ACK, "Incompatible DEAL/ACK and waiting"

    sim.release_delayed()

    while sim.remaining():
        sim.step()

    assert not any(player.waiting for player in players.values()), "Some message still waiting"
    assert not any(player.DEAL for player in players.values()), "DEAL full for somebody"
    assert not any(player.ACK for player in players.values()), "ACK full for somebody"


def test_different_values():
    sim = MWRandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players

    dealer = players[randint(1, 4)]
    mod = randint(1, 4)
    secret = randint(1, 40)
    tag = (1, 1, dealer.id, mod)
    SVSS_tag = (tag[0], tag[1])

    dealer.deal_MW(secret, 1, 1, mod)
    players[mod].MW_moderate(secret + 1, 1, 1, dealer.id)

    while sim.remaining():
        sim.step()

    for player in players.values():
        assert SVSS_tag not in player.MW_val, "Reconstructed secret impossibly"
        assert tag not in player.MW_M, "Advanced too much with impossible secret"
        assert tag not in player.MW_OK, "Advanced too much with impossible secret"


def test_SVSS():
    sim = RandomOrderSimulator()
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players

    dealer = players[randint(1, 4)]
    secret = randint(1, 40)

    dealer.deal_SVSS(secret)

    while sim.remaining():
        sim.step()

    # for player in players.values():
    #     if (2, dealer.id) not in player.SVSS_val:
    #         player.check_SVSS_rec_done((2, dealer.id))

    for player in players.values():
        assert (2, dealer.id) in player.SVSS_val, "No secret reconstructed"
        assert player.SVSS_val[(2, dealer.id)] == secret, "Wrong secret reconstructed"


def test_SVSS_correct_RB():
    n = 4
    t = 1
    sim = RBRandomOrderSimulator(n, t)
    players = {i: Player(sim, i, n, t) for i in range(1, n + 1)}
    sim.players = players

    dealer = players[randint(1, n)]
    secret = randint(1, 40)

    dealer.deal_SVSS(secret)

    while sim.remaining():
        sim.step()

    for player in players.values():
        assert (2, dealer.id) in player.SVSS_val, "No secret reconstructed"
        assert player.SVSS_val[(2, dealer.id)] == secret, "Wrong secret reconstructed"


def test_SVSS_evil_player():
    n = 4
    t = 1
    sim = RBRandomOrderSimulator(n, t)
    players = {i: Player(sim, i, n, t) for i in range(1, n + 1)}
    evil_player = EvilPlayer(sim, 4, 4, 1)
    players[4] = evil_player
    sim.players = players

    dealer = players[randint(1, n)]
    secret = randint(1, 40)
    tag = (2, dealer.id)

    dealer.deal_SVSS(secret)

    while sim.remaining():
        sim.step()

    assert all(tag in player.SVSS_val for player in players.values()), "No secret reconstructed"

    if all(player.SVSS_val[tag] is not None for player in players.values()):
        assert all(player.SVSS_val[tag] == secret for player in players.values()), "No secret reconstructed"
    else:
        assert any(evil_player.id in player.D for player in players.values()), "Wrong secret, but didn't update D"


def test_SVSS_sevreal_runs():
    sim = RBRandomOrderSimulator(4, 1)
    players = {i: Player(sim, i, 4, 1) for i in range(1, 4 + 1)}
    sim.players = players
    runs = 5

    def helper(i):
        dealer = players[randint(1, 4)]
        secret = randint(1, 40)
        dealer.deal_SVSS(secret)

        tag = (dealer.c, dealer.id)
        return dealer, secret, tag

    dealer = []
    secret = []
    tag = []


    for i in range(runs):
        data = helper(i)

        dealer.append(data[0])
        secret.append(data[1])
        tag.append(data[2])

    while sim.remaining():
        sim.step()

    for i in range(runs):
        assert all(tag[i] in player.SVSS_val for player in players.values()), "No secret reconstructed"
        assert all(player.SVSS_val[tag[i]] == secret[i] for player in players.values()), "Wrong secret reconstructed"


def test_delay_message():
    player = Player(None, 1, 4, 1)

    tag = (1, 1)
    message = Message(None, (1, 1), 2, Stage.SVSS_VALUES)

    early = 0
    before = 5
    early_mid = 13
    late_mid = 17
    after = 25
    late = 30

    times = [[before, early_mid], [early_mid, after], [early_mid, late_mid], [before, after], [early, before],
             [after, late], [early, None], [early_mid, None], [after, None]]

    values = [False] * 9

    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    second_tag = (2, 2)
    player.invocations[second_tag] = [10, None]

    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    player.DEAL[second_tag] = {2: 1}

    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    player.ACK[second_tag] = {(1,2): 1}
    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    player.DEAL.pop(second_tag)
    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]
    player.ACK.pop(second_tag)

    player.invocations[second_tag] = [10, 20]

    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    values[5] = True
    values[8] = True

    player.DEAL[second_tag] = {2: 1}

    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    player.ACK[second_tag] = {(1,2): 1}
    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]

    player.DEAL.pop(second_tag)
    for i in range(len(times)):
        player.invocations[tag] = times[i]
        assert player.delay_message(message, tag) == values[i]
    player.ACK.pop(second_tag)
