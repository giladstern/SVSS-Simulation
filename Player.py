from Polynomial import *
from Message import *


class Player:
    def __init__(self, simulator, id, n, t):
        # Assume this processor is P_i
        self.simulator = simulator
        self.id = id
        self.c = 0
        self.D = set()
        self.ACK = {}  # {tag: {(dealer, processor): f_dealer(processor)}. The Ack set from the protocol.
        self.DEAL = {}  # {tag: {sender: data}}. The DATA set from the protocol.
        self.waiting = []  # Messages waiting from DMM.
        self.invocations = {}  # [(begin_time, end_time)]. If an invocation hasn't ended there will be None.
        self.n = n
        self.players = range(1, n+1)
        self.t = t
        self.field = n ** 2
        self.MW_data = {}  # {tag: (polynomial, {j: f_j(i)}}. The data received from the dealer.
        self.MW_mod_data = {}  # {tag: polynomial}. The moderator's data received for the MW session.
        self.MW_corroborate = {}  # {tag: {j: f_i(j)}. Data received which agrees with P_i's data.
        # If messages are received before receiving the relevant data, the messages are stored instead of dictionaries.
        self.MW_ack = {}  # {tag: {processors1, ...}}. Processors who've sent acks.
        self.MW_L = {}  # {tag: {j : {processor1, ...}}. Each processor's L set.
        self.MW_mod_M = {}  # {tag: {processor1, ...}}. The moderator's accumulating M sets.
        self.MW_mod_corroborate = {}  # {tag: {processor1, ...}}. Processors who've agreed with the moderator.
        # MW_mod_corroborate is the intersection of MW_ack and MW_mod_corroborate.
        # If messages are received before receiving the relevant data, the messages are stored instead of processors.
        self.MW_M = {}  # {tag: {processor1, ...}}. The received M sets.
        self.MW_secret_polys = {}  # {tag: (f, {j: f_j})}. The dealer's sampled polynomials.
        self.MW_OK = set()  # {tag1, tag2, ...}. Tags for which an OK message has been received.
        self.MW_share_done = set()  # {tag1, tag2, ...} . Tags for which the MW-Share protocol is done.
        self.MW_K = {}  # {tag: {dealer_index: [(moderator_index, f_dealer(moderator)]}. The K sets for reconstructions.
        self.MW_waiting_K = {}  # {tag: [message1, message2, ...]. K messages waiting to be processed.
        self.MW_val = {}  # {SVSS_tag: {dealer: val}}. Reconstructed values, indexed by the relevant SVSS tag.
        self.MW_mod_value = {}  # {tag: val}. The value used by the moderator for the relevant MW-SVSS invocation.
        # If a message is received before calling the moderate function there is a message instead of a value.
        self.MW_reconstruct_started = set()  # {tag1, tag2, ...}. Tags for which reconstruct has started.
        self.G = {}  # {tag: {dealer: {moderator1, moderator2, ...}}. The G set from the protocol.
        self.S = {}  # {tag: {processor1, processor2, ...}}. The S_(t+1) set from the protocol.
        self.G_dealer = {}  # {tag: {dealer: {moderator1, moderator2, ...}}. The G set accumulated by the dealer.
        self.G_sent = set()  # {tag1, tag2, ...}. The SVSS invocations for which the G set has been sent.
        self.SVSS_share_done = set() # {tag1, tag2, ...}. Tags for which the SVSS-Share protocol is done.
        self.SVSS_val = {}  # {tag: val}. The reconstructed values for SVSS.

    def DMM(self, message):
        """
        This function filters, delays, or forwards a message to processing.
        In general, the receive function should never be called from outside, only DMM.
        """
        tag = message.tag

        check_waiting = False
        # Compare to ACK and DEAL, update the sets if necessary and D if a lie was detected.
        if message.RB and message.stage == Stage.MW_REC:
            point = (message.content[0], message.sender)
            if tag in self.ACK and point in self.ACK[tag]:
                if self.ACK[tag][point] == message.content[1]:
                    self.ACK[tag].pop(point)
                    check_waiting = True
                    if not self.ACK[tag]:
                        self.ACK.pop(tag)
                else:
                    self.D.add(message.sender)

            if tag in self.DEAL and message.sender in self.DEAL[tag] and message.content[0] == self.id:
                if self.DEAL[tag][message.sender] == message.content[1]:
                    self.DEAL[tag].pop(message.sender)
                    check_waiting = True
                    if not self.DEAL[tag]:
                        self.DEAL.pop(tag)
                else:
                    self.D.add(message.sender)

        # RB messages are always processed if received. They should reach DMM only after enough processors participate.
        if message.RB:
            self.receive(message)

        elif message.sender not in self.D:
            if self.delay_message(message, tag):
                self.waiting.append(message)
            else:
                self.receive(message)

        # If DEAL or ACK have been updated, we need to check if some waiting messages should be processed.
        if check_waiting:
            to_receive = []
            for message in self.waiting:
                tag = message.tag

                if not self.delay_message(message, tag):
                    to_receive.append(message)

            self.waiting = [message for message in self.waiting if message not in to_receive]
            for message in to_receive:
                self.receive(message)

    def delay_message(self, message, tag):
        return self.delay_helper(message, tag, self.ACK, lambda x: x[1]) or self.delay_helper(message, tag, self.DEAL)

    def delay_helper(self, message, tag, check_against, key=lambda x: x):
        sender = message.sender

        for check_tag in check_against:
            if self.invocations[check_tag][1] is None:
                continue

            for elem in check_against[check_tag]:
                if sender == key(elem) and ((self.invocations[check_tag][1] and tag not in self.invocations)
                                            or self.invocations[check_tag][1] < self.invocations[tag][0]):
                    return True

        return False

    def send(self, message, to):
        if self.simulator:
            self.simulator.send(message, to)

    def RB(self, message):
        message.RB = True
        if self.simulator:
            self.simulator.RB(message)

    def deal_MW(self, secret, c, SVSS_d, moderator):
        """
        This function deals an MW secret.
        Thie function shouldn't be called from outside, but after receiving values for an SVSS-Share.
        """
        time = self.simulator.time()
        tag = (c, SVSS_d, self.id, moderator)
        self.invocations[tag] = [time, None]

        f = Polynomial.random_polynomial(secret, self.t, self.field)
        polys = {i: Polynomial.random_polynomial(f.eval(i), self.t, self.field) for i in self.players}

        for i in self.players:
            content = (polys[i], {j: polys[j].eval(i) for j in self.players})
            message = Message(content, tag, self.id, Stage.MW_VALUES, moderator)

            self.send(message, i)

        mod_message = Message(f, tag, self.id, Stage.MW_VALUES, moderator)
        self.send(mod_message, moderator)
        self.ACK[tag] = {}
        self.MW_secret_polys[tag] = (f, polys)

    def receive(self, message):
        """
        Throughout this simulation, I'm assuming that all messages sent are of the correct format.
        Anything with an incorrect format would not have been sent.
        This could technically be checked in the simulator.
        Also, for now I'm assuming there is only one message sent for every stage.
        """

        if message.stage <= Stage.MW_REC and message.tag not in self.invocations:
            self.invocations[message.tag] = [self.simulator.time(), None]
        elif message.tag not in self.invocations:
            self.invocations[message.tag] = [self.simulator.time(), None]

        if message.stage <= Stage.MW_OK and message.tag not in self.MW_share_done:
            if message.stage == Stage.MW_VALUES:
                self.receive_mw_values(message)
            elif message.stage == Stage.MW_CORROBORATE:
                self.receive_mw_corroborate(message)
            elif message.stage == Stage.MW_ACK and message.RB:
                self.receive_mw_ack(message)
            elif message.stage == Stage.MW_L and message.RB:
                self.receive_MW_L(message)
            elif message.stage == Stage.MW_L and self.id == message.moderator:
                self.receive_MW_L_mod(message)
            elif message.stage == Stage.MW_M and message.sender == message.moderator and message.RB:
                self.receive_MW_M(message)
            elif message.stage == Stage.MW_OK and message.sender == message.tag[2] and message.RB:
                self.receive_MW_OK(message)
        elif message.stage == Stage.MW_REC and message.RB:
            self.receive_MW_rec(message)
        elif message.stage == Stage.SVSS_VALUES and message.tag[1] == message.sender:
            self.receive_SVSS_values(message)
        elif message.stage == Stage.SVSS_G and message.tag[1] == message.sender and message.RB:
            self.receive_SVSS_G(message)

    def MW_moderate(self, val, c, SVSS_d, MW_d):
        """
        This function moderates an MW-Share protocol.
        The function shouldn't be called from outside, but after receiving values for an SVSS-Share
        """
        tag = (c, SVSS_d, MW_d, self.id)

        if tag in self.MW_mod_value:
            message = self.MW_mod_value[tag]
            self.MW_mod_value[tag] = val
            self.receive(message)
        else:
            self.MW_mod_value[tag] = val

    def receive_mw_values(self, message):
        """ This is to be called when receiving the original values for an MW session. """
        tag = message.tag

        # There was a slight overloading of the MW_VALUES stage.
        # Messages for the dealer and for processors get the same stage signifier.
        if type(message.content) == Polynomial and self.id == message.moderator:
            if tag not in self.MW_mod_value:
                self.MW_mod_value[tag] = message
                return

            if self.MW_mod_value[tag] != message.content.eval(0):
                return

            self.MW_mod_data[tag] = message.content
            self.MW_mod_M[tag] = set()

            messages = []
            if tag in self.MW_mod_corroborate:
                messages = self.MW_mod_corroborate[tag]

            self.MW_mod_corroborate[tag] = set()
            for message in messages:
                self.receive_MW_L_mod(message)

        else:
            self.MW_data[tag] = message.content
            self.DEAL[tag] = {}
            ack = Message(None, message.tag, self.id, Stage.MW_ACK, message.moderator)
            self.RB(ack)
            for i in self.players:
                data_message = Message(message.content[1][i], message.tag, self.id,
                                       Stage.MW_CORROBORATE, message.moderator)
                self.send(data_message, i)

            if tag not in self.MW_ack:
                self.MW_ack[tag] = set()

            if tag in self.MW_corroborate:
                messages = self.MW_corroborate[tag]
                self.MW_corroborate[tag] = {}
                for message in messages:
                    self.receive_mw_corroborate(message)
            else:
                self.MW_corroborate[tag] = {}

    def receive_mw_ack(self, message):
        """ This function is to be called after receiving an ack message. """

        tag = message.tag
        if tag not in self.MW_ack:
            self.MW_ack[tag] = set()

        self.MW_ack[tag].add(message.sender)

        self.process_mw_ack_corr(tag, message.sender)

        if message.moderator == self.id:
            self.process_mw_ack_L(tag, message.sender)

        if tag[2] == self.id:
            self.dealer_check_ok(tag)

        self.check_MW_share_done(tag)

    def receive_mw_corroborate(self, message):
        """ This function is to be called after receiving a message with corroborating data. """

        tag = message.tag
        sender = message.sender

        if tag in self.MW_data:
            if self.MW_data[tag][0].eval(sender) == message.content:
                self.MW_corroborate[tag][sender] = message.content
                self.process_mw_ack_corr(tag, sender)
        else:
            if tag not in self.MW_corroborate:
                self.MW_corroborate[tag] = []
            self.MW_corroborate[tag].append(message)

    def process_mw_ack_corr(self, tag, sender):
        """
        This function is to be called after either receiving an ack or a corroborating message.
        If both an ack message and a corroborating message has been received, this function updates DEAL.
        It also sends an L message if necessary.
        """

        mod = tag[3]
        if tag not in self.DEAL:
            self.DEAL[tag] = {}
        if tag in self.MW_data and sender in self.MW_corroborate[tag] and sender in self.MW_ack[tag]\
                and len(self.DEAL[tag]) < self.n - self.t:
            self.DEAL[tag][sender] = self.MW_corroborate[tag].pop(sender)

            if len(self.DEAL[tag]) == self.n - self.t:
                message = Message(set(self.DEAL[tag].keys()), tag, self.id, Stage.MW_L, mod, RB=True)
                self.RB(message)

                poly = self.MW_data[tag][0]
                mod_message = Message(poly.eval(0), tag, self.id, Stage.MW_L, mod)
                self.send(mod_message, mod)

    def receive_MW_L(self, message):
        """ This function is to be called after receiving an L message. """

        if len(message.content) >= self.n - self.t:
            tag = message.tag

            if tag not in self.MW_L:
                self.MW_L[tag] = {}

            self.MW_L[tag][message.sender] = message.content

            if message.moderator == self.id:
                self.process_mw_ack_L(tag, message.sender)

            if message.tag[2] == self.id:
                self.dealer_check_ok(tag)

            self.check_MW_share_done(tag)

    def receive_MW_L_mod(self, message):
        """ This function is to be called after a moderator receives an L message. """

        tag = message.tag

        if tag not in self.MW_mod_corroborate:
            self.MW_mod_corroborate[tag] = set()

        if tag in self.MW_mod_data:
            if self.MW_mod_data[tag].eval(message.sender) == message.content:
                self.MW_mod_corroborate[tag].add(message.sender)
        else:
            self.MW_mod_corroborate[tag].add(message)

        self.process_mw_ack_L(tag, message.sender)

    def process_mw_ack_L(self, tag, sender):
        """
        This function is to be called by a moderator after receiving an ack or an L message.
        The function checks if a particular processor sent both and if it did, it updates the internal M set.
        Also, if M is large enough, the function sends a message with M.
        """

        mod = tag[3]
        if tag in self.MW_mod_data and tag in self.MW_mod_corroborate and sender in self.MW_mod_corroborate[tag] and \
                tag in self.MW_ack and sender in self.MW_ack[tag] and tag in self.MW_mod_M and \
                len(self.MW_mod_M[tag]) < self.n - self.t:

            self.MW_mod_M[tag].add(sender)
            if len(self.MW_mod_M[tag]) == self.n - self.t:
                message = Message(self.MW_mod_M[tag], tag, self.id, Stage.MW_M, mod, True)
                self.RB(message)

    def receive_MW_M(self, message):
        """ This function is to be called after receiving an M message. """

        tag = message.tag

        if len(message.content) >= self.n - self.t:
            self.MW_M[tag] = message.content

            if message.tag[0] == self.id:
                self.dealer_check_ok(tag)

            if message.tag[2] == self.id:
                self.dealer_check_ok(tag)

            self.check_MW_share_done(tag)

    def dealer_check_ok(self, tag):
        """
        This function is to be called only by an MW-SVSS dealer.
        This function should be called after receiving an M message, an ack message, or an L message.
        This function checks if the share is done and if so it sends a message
        """

        if tag in self.MW_M and tag in self.MW_L and tag in self.MW_ack and tag in self.ACK:
            for j in self.MW_M[tag]:
                if j not in self.MW_L[tag]:
                    return
                for l in self.MW_L[tag][j]:
                    if l not in self.MW_ack[tag]:
                        return

            for j in self.MW_M[tag]:
                for l in self.MW_L[tag][j]:
                    self.ACK[tag][(j, l)] = self.MW_secret_polys[tag][1][j].eval(l)

            message = Message(None, tag, self.id, Stage.MW_OK, tag[3], True)
            self.RB(message)

    def check_MW_share_done(self, tag):
        """
        This function is to be called after receiving an OK, M, L or ack message.
        The function checks if all of the relevant data has been received and is correct.
        If all of the data has been received, the MW_share_done set is updated.
        Also, if the share is done, the function checks if the relevant SVSS share is done.
        """
        if tag in self.MW_OK and tag in self.MW_M and tag in self.MW_L and tag in self.MW_ack:
            if self.id not in self.MW_M[tag] and tag in self.DEAL:
                self.DEAL.pop(tag)
            for l in self.MW_M[tag]:
                if l not in self.MW_L[tag]:
                    return
                for k in self.MW_L[tag][l]:
                    if k not in self.MW_ack[tag]:
                        return
            self.MW_share_done.add(tag)
            self.check_SVSS_share_done(tag)

    def receive_MW_OK(self, message):
        """ This function is to be called if an OK message is received. """
        tag = message.tag
        self.MW_OK.add(tag)
        self.check_MW_share_done(tag)

    def MW_reconstruct(self, tag):
        """
        This function is to be called when an MW-Reconstruct should be called.
        In general we expect this to only by called during the relevant SVSS-Reconstruct.
        """

        if tag in self.MW_reconstruct_started:
            return

        self.MW_reconstruct_started.add(tag)
        messages = []

        if tag in self.MW_waiting_K:
            messages = self.MW_waiting_K[tag]
            self.MW_waiting_K.pop(tag)
        self.MW_K[tag] = {l: [] for l in self.MW_M[tag]}

        for message in messages:
            self.receive(message)

        for l in self.MW_M[tag]:
            if self.id in self.MW_L[tag][l]:
                val = self.MW_data[tag][1][l]
                message = Message((l, val), tag, self.id, Stage.MW_REC, tag[3], True)
                self.RB(message)

    def receive_MW_rec(self, message):
        """
        This function is to be called when values are received during the MW-Reconstruct protocol.
        If values are received after starting the reconstruction, then MW_K is updated.
        If values are received before starting the reconstruction, MW_waiting_K is updated.
        The function also checks if the reconstruction is complete.
        """
        l, val = message.content
        tag = message.tag

        if tag not in self.MW_K:
            if tag not in self.MW_waiting_K:
                self.MW_waiting_K[tag] = []
            self.MW_waiting_K[tag].append(message)
            return

        if l not in self.MW_M[tag] or message.sender not in self.MW_L[tag][l]:
            return

        if len(self.MW_K[tag][l]) < self.t + 1:
            self.MW_K[tag][l].append((message.sender, val))

        self.check_MW_reconstruction(tag)

    def check_MW_reconstruction(self, tag):
        """
        This function is to be called after receiving any value for the reconstruction,
        but only after starting the reconstruction.
        If the reconstruction is complete then both the MW_val and invocations data structures are updated.
        """
        if tag in self.MW_val:
            return

        for l in self.MW_K[tag]:
            if len(self.MW_K[tag][l]) < self.t + 1:
                return

        points = []

        SVSS_tag = (tag[0], tag[1])
        dealer = tag[2]
        mod = tag[3]

        if SVSS_tag not in self.MW_val:
            self.MW_val[SVSS_tag] = {}

        if dealer not in self.MW_val[SVSS_tag]:
            self.MW_val[SVSS_tag][dealer] = {}

        for l in self.MW_K[tag]:
            poly = Polynomial.interpolate(self.MW_K[tag][l])
            if poly.deg > self.t:

                self.set_MW_value(None, SVSS_tag, dealer, mod)
                return

            points.append((l,poly.eval(0)))

        self.invocations[tag][1] = self.simulator.time()

        poly = Polynomial.interpolate(points)

        if SVSS_tag not in self.MW_val:
            self.MW_val[SVSS_tag] = {}

        if poly.deg > self.t:
            self.set_MW_value(None, SVSS_tag, dealer, mod)
        else:
            self.set_MW_value(poly.eval(0), SVSS_tag, dealer, mod)

    def set_MW_value(self, val, pseudo_SVSS_tag, dealer, mod):
        """
        This function should be called in order to add a value to MW_val instead of setting it directly.
        The function also checks if the relevant SVSS-Reconstruct invocation has been completed.
        """
        self.MW_val[pseudo_SVSS_tag][dealer][mod] = val
        SVSS_tag = (pseudo_SVSS_tag[0] - pseudo_SVSS_tag[0] % 2, pseudo_SVSS_tag[1])
        self.check_SVSS_rec_done(SVSS_tag)

    def deal_SVSS(self, secret):
        """
        This function deals a secret with the surrent processor as dealer.
        """
        self.c += 2
        poly = BivariatePolynomial.random_polynomial(secret, self.t, self.field)
        tag = (self.c, self.id)
        self.invocations[tag] = [self.simulator.time(), None]

        for player in self.players:
            g = poly.g(player)
            h = poly.h(player)

            message = Message((g, h), tag, self.id, Stage.SVSS_VALUES)
            self.send(message, player)

    def receive_SVSS_values(self, message):
        """
        This function is to be called after receiving values for an SVSS-Share invocation.
        The function calls all of MW-Share protocols as both dealer and moderator.
        """

        # Refactored once in order to have the dealer and moderator of MW-SVSS in the tag.
        # Realized we need different tags for the g and h values, instead I'm going to use a trick.
        # The counter c is going to go up by 2 each time and then even c values are going to signify
        # the g value, whereas odd c values are going to signify the h values.

        g = message.content[0]
        h = message.content[1]
        for player in self.players:
            self.deal_MW(g.eval(player), message.tag[0], message.tag[1], player)
            self.deal_MW(h.eval(player), message.tag[0] + 1, message.tag[1], player)
            self.MW_moderate(g.eval(player), message.tag[0] + 1, message.tag[1], player)
            self.MW_moderate(h.eval(player), message.tag[0], message.tag[1], player)

    def check_SVSS_share_done(self, tag):
        """
        This function is to be called after completing any MW-Share invocation, or after receiving G and S.
        If the current processor is the dealer, the function will check if the G and S sets are large enough and
        if so, messages completing the protocol will be sent.
        Regardless, the function checks if correct G and S messages have been received, and all of the relevant
        MW-Share invocations are done, and if so proceeds to the SVSS-Reconstruct protocol.
        """
        if tag[1] == self.id:
            self.dealer_check_SVSS_share_done(tag)

        SVSS_tag = (tag[0] - tag[0] % 2, tag[1])
        self.participant_check_SVSS_share_done(SVSS_tag)

    def dealer_check_SVSS_share_done(self, tag):
        """
        This function is to be called by a dealer after having received any MW-Share invocation.
        After completing enough invocations, G and S sets are sent (as described in the protocol).
        """
        SVSS_tag = (tag[0] - tag[0] % 2, tag[1])
        if SVSS_tag in self.G_sent:
            return

        if SVSS_tag not in self.G_dealer:
            self.G_dealer[SVSS_tag] = {}
            for player in self.players:
                self.G_dealer[SVSS_tag][player] = set()

        self.add_to_G_dealer(tag)

        S = [set([p for p in self.players])]
        S += [set() for i in range(self.t+1)]

        for i in range(self.t + 1):
            for j in S[i]:
                if len(self.G_dealer[SVSS_tag][j].intersection(S[i])) >= self.n - self.t:
                    S[i + 1].add(j)

        if len(S[-1]) >= self.n - self.t:
            self.G_sent.add(SVSS_tag)

            content = (S, self.G_dealer[SVSS_tag])
            message = Message(content, SVSS_tag, self.id, Stage.SVSS_G, RB=True)
            self.RB(message)

    def participant_check_SVSS_share_done(self, tag):
        """
        This function is to be called after either receiving S and G sets, or completing any MW-Share invocation.
        The function checks if the SVSS-Share invocation is done, and if so continues to SVSS-Reconstruct.
        """
        if tag not in self.G:
            return
        self.helper_SVSS_share_done(tag)

    def add_to_G_dealer(self, tag):
        """
        This is a helper function for adding two processors to each other's G_j sets.
        It checks if all relevant MW-Share invocations have been completed.
        """
        c = tag[0] - tag[0] % 2
        d = tag[1]
        SVSS_d = tag[2]
        SVSS_m = tag[3]
        SVSS_tag = (c, d)

        if (c, d, SVSS_d, SVSS_m) in self.MW_share_done and (c + 1, d, SVSS_d, SVSS_m) in self.MW_share_done \
            and (c, d, SVSS_m, SVSS_d) in self.MW_share_done and (c + 1, d, SVSS_m, SVSS_d):
            self.G_dealer[SVSS_tag][SVSS_m].add(SVSS_d)
            self.G_dealer[SVSS_tag][SVSS_d].add(SVSS_m)

    def receive_SVSS_G(self, message):
        """
        This function is to be called after receiving G and S from a dealer.
        If the sets aren't correct the function doesn't proceed and leaves the internal data structures in a state
        where the SVSS-Share protocol never completes.
        """
        S, G = message.content

        if S[0] != set([p for p in self.players]):
            return

        if len(S) != self.t + 2:
            return

        if len(S[self.t + 1]) < self.n - self.t:
            return

        for i in range(self.t + 1):
            for j in S[i + 1]:
                if len(G[j].intersection(S[i])) < self.n - self.t:
                    return

        for j in G:
            for k in G[j]:
                if j not in G[k]:
                    return

        self.G[message.tag] = G
        self.S[message.tag] = S[-1]
        self.helper_SVSS_share_done(message.tag)

    def helper_SVSS_share_done(self, tag):
        """
        This function is a helper function called after completing a relevant MW-Share or receiving G and S.
        """
        tag = (tag[0] - tag[0] % 2, tag[1])
        if tag in self.SVSS_share_done:
            return

        c = tag[0]
        d = tag[1]

        for i in self.G[tag]:
            for j in self.G[tag][i]:
                if (c, d, i, j) not in self.MW_share_done or (c, d, j, i) not in self.MW_share_done or\
                        (c + 1, d, i, j) not in self.MW_share_done or (c + 1, d, j, i) not in self.MW_share_done:
                    return

        self.SVSS_share_done.add(tag)
        self.SVSS_reconstruct(tag)

    def SVSS_reconstruct(self, tag):
        """
        This function is automatically called after completing the corresponding SVSS-Share invocation.
        It starts all of the relevant MW-Reconstruct invocations as well.
        """
        c = tag[0]
        d = tag[1]

        for i in self.G[tag]:
            for j in self.G[tag][i]:
                self.MW_reconstruct((c, d, i, j))
                self.MW_reconstruct((c, d, j, i))
                self.MW_reconstruct((c + 1, d, i, j))
                self.MW_reconstruct((c + 1, d, j, i))

    def check_SVSS_rec_done(self, SVSS_tag):
        """
        This function is to be called after completing any relevant MW-Reconstruct invocation.
        The function checks if all of the required MW-Reconstruct invocations have been completed.
        If all have been completed the function interpolates the required polynomials and completes the invocation.
        """
        if SVSS_tag in self.SVSS_val or SVSS_tag not in self.G:
            return

        c = SVSS_tag[0]
        d = SVSS_tag[1]

        def helper(pseudo_SVSS_tag):
            """
            This helper function returns True iff all MW-Reconstruct invocations have been completed for the dealers
            in S.
            Note that it checks only the c value in pseudo_SVSS_tag.
            That means that the function needs to be run once with c = 2k and with c = 2k + 1 for the same k.
            """
            SVSS_tag = (pseudo_SVSS_tag[0] - pseudo_SVSS_tag[0] % 2, pseudo_SVSS_tag[1])
            if pseudo_SVSS_tag not in self.MW_val or SVSS_tag not in self.G:
                return False

            for dealer in self.S[SVSS_tag]:
                if dealer not in self.MW_val[pseudo_SVSS_tag]:
                    return False

                dealer_G = self.G[SVSS_tag][dealer]
                dealer_vals = self.MW_val[pseudo_SVSS_tag][dealer]
                for mod in dealer_G:
                    if mod not in self.MW_val[pseudo_SVSS_tag]:
                        return False
                    mod_vals = self.MW_val[pseudo_SVSS_tag][mod]
                    if mod not in dealer_vals or dealer not in mod_vals:
                        return False

            return True

        if helper((c, d)) and helper((c + 1, d)):
            self.interpolate_SVSS_val(SVSS_tag)

    def interpolate_SVSS_val(self, SVSS_tag):
        """
        This function is to be called after having completed all of the relevant MW-Reconstruct invocations.
        This function interpolates the points and checks validity.
        In the end, SVSS_val is always updated, possibly with a None value.
        """
        I = set()

        c = SVSS_tag[0]
        d = SVSS_tag[1]

        g_polys = {}
        h_polys = {}

        for k in self.S[SVSS_tag]:
            g_points = []
            h_points = []
            for l in self.G[SVSS_tag][k]:
                g_val = self.MW_val[(c, d)][k][l]
                h_val = self.MW_val[(c + 1, d)][k][l]
                if g_val is None or h_val is None:
                    I.add(k)
                    break
                g_points.append((l, g_val))
                h_points.append((l, h_val))
            if k in I:
                continue

            g = Polynomial.interpolate(g_points)
            h = Polynomial.interpolate(h_points)

            if g.deg > self.t or h.deg > self.t:
                I.add(k)
            else:
                g_polys[k] = g
                h_polys[k] = h

        reconstruct_set = [i for i in self.S[SVSS_tag] if i not in I]

        if len(reconstruct_set) < self.n - self.t:
            self.SVSS_val[SVSS_tag] = None
            return

        for i in reconstruct_set:
            for j in reconstruct_set:
                if g_polys[i].eval(j) != h_polys[j].eval(i):
                    self.SVSS_val[SVSS_tag] = None
                    return

        g_points = [(i, g_polys[i].eval(0)) for i in g_polys]
        h_points = [(i, h_polys[i].eval(0)) for i in h_polys]

        g_val = Polynomial.interpolate(g_points).eval(0)
        h_val = Polynomial.interpolate(h_points).eval(0)

        if g_val != h_val:
            self.SVSS_val[SVSS_tag] = None

        else:
            self.SVSS_val[SVSS_tag] = g_val
