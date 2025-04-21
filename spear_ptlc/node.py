import hashlib
import random
from spear_ptlc import secp256k1

def random_bytes():
    return random.randbytes(32)

class PTLC:
    def __init__(self, id, amount, payment_hash, pubkey):
        self.id = id
        self.amount = amount
        self.pubkey = pubkey
        self.payment_hash = payment_hash

    def verify(self, secret):
        return secp256k1.G * secret == self.pubkey

class SecretKey:
    def __init__(self, k=None):
        self.k = k or secp256k1.Fr(random.randint(0, secp256k1.N))
    
    def pubkey(self):
        return PublicKey(secp256k1.G * self.k)

class PublicKey:
    def __init__(self, pubkey):
        self.pubkey = pubkey

    def compute_hash(self):
        return hashlib.sha256(self.pubkey.x.x.to_bytes(32, 'little') + self.pubkey.y.x.to_bytes(32, 'little')).hexdigest()
    
class Payment:
    def __init__(self, pubkey, amount, parts_count, redundant_parts_count):
        self.pubkey = pubkey
        self.payment_hash = pubkey.compute_hash()
        self.amount = amount
        self.amount_per_part = amount / parts_count
        self.locked_amount = amount + self.amount_per_part * redundant_parts_count
        self.parts_count = parts_count
        self.redundant_parts_count = redundant_parts_count
        self.ptlcs = []
        self.nonce_secrets = []

        # generate HHTLC hashes for each part
        for i in range(parts_count + redundant_parts_count):
            # generate random nonce for each hop (for simplicity we has 0 hops)
            nonce_secret = secp256k1.Fr(random.randint(0, secp256k1.N))
            pubkey = self.pubkey.pubkey + secp256k1.G * nonce_secret
            self.ptlcs.append(PTLC(i, self.amount_per_part, self.payment_hash, pubkey))
            self.nonce_secrets.append(nonce_secret)

class Invoice:
    def __init__(self, amount):
        self.secret_key = SecretKey()
        self.pubkey = self.secret_key.pubkey()
        self.amount = amount
        self.payment_hash = self.pubkey.compute_hash()

class Node:
    def __init__(self):
        self.balance = 0
        self.locked_balance = 0
        self.payments = []
        self.invoices = []
        self.received_ptlcs = []

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
        return invoice.payment_hash, invoice.pubkey, invoice.amount

    # payer gen redandent payment parts
    # return locked parts
    def pay(self, pubkey, amount, parts_count, redundant_parts_count):
        payment = Payment(pubkey, amount, parts_count, redundant_parts_count)
        self.lock_balance(payment.locked_amount)
        self.payments.append(payment)
        return payment.ptlcs

    # payer reveal preimages of payment ptlcs to payee
    def reveal_ptlcs(self, ptlcs):
        # all parts should be from the same payment
        payment_hash = None
        for ptlc in ptlcs:
            if payment_hash is None:
                payment_hash = ptlc.payment_hash
            elif payment_hash != ptlc.payment_hash:
                raise Exception("PTLCs are from different payments")
        
        # find payment
        payment = None
        for p in self.payments:
            if p.payment_hash == payment_hash:
                payment = p
                break
        if payment is None:
            raise Exception("Payment not found")
            
        # check total amount of parts
        total_amount = sum([ptlc.amount for ptlc in ptlcs])
        if total_amount != payment.amount:
            raise Exception(f"Reject to reveal ptlcs because of invalid amount {total_amount} != {payment.amount}")

        # find nonce for each part
        nonces = []
        for ptlc in ptlcs:
            payment_hash = ptlc.payment_hash
            nonce_secret = payment.nonce_secrets[ptlc.id]
            if nonce_secret is None:
                raise Exception("Payer nonce secret not found")
            # nonce is sum of all hops secret value
            # for simplicity we has 0 hops so nonce is just one secret value
            nonces.append(nonce_secret)
        
        # check nonces count
        if len(nonces) != len(ptlcs):
            raise Exception("Invalid nonces count")
        return nonces

    # payee receive locked parts
    def receive_ptlcs(self, ptlcs):
        # deduplicate parts
        for ptlc in ptlcs:
            if ptlc not in self.received_ptlcs:
                self.received_ptlcs.append(ptlc)
    
    def find_invoice(self, payment_hash):
        for invoice in self.invoices:
            if invoice.payment_hash == payment_hash:
                return invoice
        return None
    
    def find_payment(self, payment_hash):
        for payment in self.payments:
            if payment.payment_hash == payment_hash:
                return payment
        return None

    # return ptlcs or None if not enough ptlcs
    def get_received_ptlcs(self, payment_hash):
        invoice = self.find_invoice(payment_hash)
        if invoice is None:
            return None
        ptlcs = []
        total_amount = 0
        for ptlc in self.received_ptlcs:
            if ptlc.payment_hash == payment_hash:
                ptlcs.append(ptlc)
                total_amount += ptlc.amount
            if total_amount == invoice.amount:
                break
            # assume parts amount is fixed
            if total_amount > invoice.amount:
                raise Exception("Invalid payment amount")
        # check if enough parts
        if total_amount < invoice.amount:
            print(f"Not enough ptlcs, total amount: {total_amount}, invoice amount: {invoice.amount}")
            return None
        return ptlcs

    def claim(self, ptlcs, nonces):
        # check nonces count
        if len(nonces) != len(ptlcs):
            raise Exception("Invalid nonces count")
        # find invoice
        invoice = self.find_invoice(ptlcs[0].payment_hash)
        if invoice is None:
            raise Exception("Invoice not found")
        # check nonces
        secrets = []
        for index, ptlc in enumerate(ptlcs):
            print(f"Verify part {ptlc.id} payment_hash: {ptlc.payment_hash}")
            secret = invoice.secret_key.k + nonces[index]
            if not ptlc.verify(secret):
                raise Exception("Invalid secret / nonce")
            secrets.append(secret)

        # Claim payment
        print("Claim payment")
        return secrets
