import hashlib
import random

def random_bytes():
    return random.randbytes(32)

class HTLC:
    def __init__(self, amount, payment_hash, set_id):
        self.amount = amount
        self.payment_hash = payment_hash
        self.set_id = set_id

    def verify(self, preimage):
        return self.payment_hash == hashlib.sha256(preimage).hexdigest()

class Preimage:
    def __init__(self, amount, preimage, set_id):
        self.amount = amount
        self.preimage = preimage
        self.set_id = set_id

    def payment_hash(self):
        return hashlib.sha256(self.preimage).hexdigest()

class Payment:
    def __init__(self, payment_hash, amount, parts_count, redundant_parts_count):
        self.payment_hash = payment_hash
        self.set_id = random_bytes()
        self.amount = amount
        self.amount_per_part = amount / parts_count
        self.locked_amount = amount + self.amount_per_part * redundant_parts_count
        self.parts_count = parts_count
        self.redundant_parts_count = redundant_parts_count
        self.preimages = []
        self.htlcs = []

        # generate HHTLC hashes for each part
        for i in range(parts_count + redundant_parts_count):
            # payment hash is fixed (just like a normal HTLC)
            # payer preimage is random for each part
            preimage = Preimage(self.amount_per_part, random_bytes(), self.set_id)
            payment_hash = preimage.payment_hash()
            htlc = HTLC(self.amount_per_part, payment_hash, self.set_id)
            self.preimages.append(preimage)
            self.htlcs.append(htlc)

class Invoice:
    def __init__(self, amount):
        preimage = random_bytes()
        self.amount = amount
        self.payment_hash = hashlib.sha256(preimage).hexdigest()

class Node:
    def __init__(self):
        self.balance = 0
        self.locked_balance = 0
        self.payments = []
        self.invoices = []
        self.received_htlcs = []

    # lock balance
    def lock_balance(self, amount):
        if self.balance < amount:
            raise Exception("Insufficient balance")
        self.balance -= amount
        self.locked_balance += amount

    # unlock balance
    def unlock_balance(self, amount):
        if self.locked_balance < amount:
            raise Exception("Insufficient locked balance")
        self.locked_balance -= amount
        self.balance += amount

    # payee create new invoice
    # return payment hash and amount
    def new_invoice(self, amount):
        invoice = Invoice(amount)
        self.invoices.append(invoice)
        return invoice.payment_hash, invoice.amount

    # payer gen redandent payment parts
    # return locked parts
    def pay(self, payment_hash, amount, parts_count, redundant_parts_count):
        payment = Payment(payment_hash, amount, parts_count, redundant_parts_count)
        self.lock_balance(payment.locked_amount)
        self.payments.append(payment)
        return payment.htlcs

    # payer reveal preimages of payment htlcs to payee
    def reveal_htlcs(self, htlcs):
        # all parts should be from the same payment
        set_id = None
        for htlc in htlcs:
            if set_id is None:
                set_id = htlc.set_id
            elif set_id != htlc.set_id:
                raise Exception("HTLCs are from different payments")
        
        # find payment
        payment = None
        for p in self.payments:
            if p.set_id == set_id:
                payment = p
                break
        if payment is None:
            raise Exception("Payment not found")
            
        # check total amount of parts
        total_amount = sum([htlc.amount for htlc in htlcs])
        if total_amount != payment.amount:
            raise Exception(f"Reject to reveal htlcs because of invalid amount {total_amount} != {payment.amount}")

        # find payer preimages for each part
        preimages = []
        for htlc in htlcs:
            payment_hash = htlc.payment_hash
            preimage = None
            for p in payment.preimages:
                if p.payment_hash() == payment_hash:
                    preimage = p.preimage
                    break
            if preimage is None:
                raise Exception("Payer preimage not found")
            preimages.append(preimage)
        
        # check preimages count
        if len(preimages) != len(htlcs):
            raise Exception("Invalid preimages count")
        return preimages

    # payee receive locked parts
    def receive_htlcs(self, htlcs):
        # deduplicate parts
        for htlc in htlcs:
            if htlc not in self.received_htlcs:
                self.received_htlcs.append(htlc)
    
    def find_invoice(self, payment_hash):
        for invoice in self.invoices:
            if invoice.payment_hash == payment_hash:
                return invoice
        return None

    # return htlcs or None if not enough htlcs
    def get_received_htlcs(self, payment_hash, set_id):
        invoice = self.find_invoice(payment_hash)
        if invoice is None:
            return None
        htlcs = []
        total_amount = 0
        for htlc in self.received_htlcs:
            if htlc.set_id == set_id:
                htlcs.append(htlc)
                total_amount += htlc.amount
            if total_amount == invoice.amount:
                break
            # assume parts amount is fixed
            if total_amount > invoice.amount:
                raise Exception("Invalid payment amount")
        # check if enough parts
        if total_amount < invoice.amount:
            print(f"Not enough htlcs, total amount: {total_amount}, invoice amount: {invoice.amount}")
            return None
        return htlcs

    def claim(self, locked_parts, preimages):
        # check preimages count
        if len(preimages) != len(locked_parts):
            raise Exception("Invalid preimages count")
        # check preimages
        for index, part in enumerate(locked_parts):
            print(f"Verify part {index} payment_hash: {part.payment_hash}")
            if not part.verify(preimages[index]):
                raise Exception("Invalid preimage")

        # Claim payment
        print("Claim payment")
