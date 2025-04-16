class LockedPart:
    def __init__(self, amount, payment_hash, payer_hash):
        self.amount = amount
        self.payment_hash = payment_hash
        self.payer_hash = payer_hash
    
    def verify(self, preimage, payer_preimage):
        return self.payment_hash == hashlib.sha256(preimage.encode()).hexdigest() and self.payer_hash == hashlib.sha256(payer_preimage.encode()).hexdigest()

class Part:
    def __init__(self, amount, payer_preimage):
        self.amount = amount
        self.payer_preimage = payer_preimage

    def payer_hash(self):
        return hashlib.sha256(self.payer_preimage.encode()).hexdigest()

class Payment:
    def __init__(self, payment_hash, amount, parts_count, redundant_parts_count):
        self.payment_hash = payment_hash
        self.amount = amount
        self.amount_per_part = amount / parts_count
        self.locked_amount = amount + self.amount_per_part * redundant_parts_count
        self.parts_count = parts_count
        self.redundant_parts_count = redundant_parts_count
        self.parts = []
        self.locked_parts = []

        # generate HHTLC hashes for each part
        for i in range(parts_count + redundant_parts_count):
            # payment hash is fixed (just like a normal HTLC)
            # payer preimage is random for each part
            payer_preimage = uuid.uuid4()
            part = Part(self.amount_per_part, payer_preimage)
            payer_hash = part.payer_hash()
            locked_part = LockedPart(self.amount_per_part, self.payment_hash, payer_hash)
            self.parts.append(part)
            self.locked_parts.append(locked_part)

class Invoice:
    def __init__(self, amount):
        self.preimage = uuid.uuid4()
        self.amount = amount
        self.payment_hash = hashlib.sha256(self.preimage.encode()).hexdigest()

class Node:
    def __init__(self):
        self.balance = 0
        self.locked_balance = 0
        self.payments = []
        self.invoices = []
        self.received_parts = []

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
        return payment.locked_parts

    # payer reveal preimages of payment parts to payee
    def reveal_parts(self, locked_parts):
        # all parts should be from the same payment
        payment_hash = None
        for part in locked_parts:
            if payment_hash is None:
                payment_hash = part.payment_hash
            elif payment_hash != part.payment_hash:
                raise Exception("Parts are from different payments")
        
        # find payment
        payment = None
        for p in self.payments:
            if p.payment_hash == payment_hash:
                payment = p
                break
        if payment is None:
            raise Exception("Payment not found")
            
        # check total amount of parts
        total_amount = sum([part.amount for part in locked_parts])
        if total_amount > payment.amount:
            raise Exception("Invalid payment amount")

        # find payer preimages for each part
        payer_preimages = []
        for part in locked_parts:
            payer_hash = part.payer_hash
            payer_preimage = None
            for p in payment.parts:
                if p.payer_hash() == payer_hash:
                    payer_preimage = p.payer_preimage
                    break
            if payer_preimage is None:
                raise Exception("Payer preimage not found")
            payer_preimages.append(payer_preimage)
        
        # check preimages count
        if len(payer_preimages) != len(locked_parts):
            raise Exception("Invalid preimages count")
        return payer_preimages

    # payee receive locked parts
    def receive_parts(self, locked_parts):
        # deduplicate parts
        for part in locked_parts:
            if part not in self.received_parts:
                self.received_parts.append(part)
    
    def find_invoice(self, payment_hash):
        for invoice in self.invoices:
            if invoice.payment_hash == payment_hash:
                return invoice
        return None

    # return parts or None if not enough parts
    def get_received_parts(self, payment_hash):
        invoice = self.find_invoice(payment_hash)
        if invoice is None:
            return None
        parts = [p for p in self.received_parts if p.payment_hash == payment_hash]
        if len(parts) < invoice.parts_count:
            return None
        return parts[:invoice.parts_count]

    def claim(self, locked_parts, payer_preimages):
        payment_hash = locked_parts[0].payment_hash
        # get preimage from invoices
        preimage = None
        for invoice in self.invoices:
            if invoice.payment_hash == payment_hash:
                preimage = invoice.preimage
                break
        if preimage is None:
            raise Exception("Preimage not found")
        # check preimages count
        if len(payer_preimages) != len(locked_parts):
            raise Exception("Invalid preimages count")
        # check preimages
        for index, part in enumerate(locked_parts):
            if not part.verify(preimage, payer_preimages[index]):
                raise Exception("Invalid preimage")

        # Claim payment
        print("Claim payment")
