import random
from spear_ptlc.node import Node, SecretKey

def run_test():
    print("Running Spear PTLC protocol test...")
    
    # 0. Setup two nodes: payer and payee
    payer = Node()
    payee = Node()
    
    # Add some balance to payer
    payer.balance = 1000
    
    # 1. Payee creates invoice
    amount = 100
    payment_hash, pubkey, _ = payee.new_invoice(amount)
    print(f"Payee created invoice with payment hash: {payment_hash}")
    
    # 2. Payer pays invoice
    parts_count = 5
    redundant_parts_count = 2
    ptlcs = payer.pay(pubkey, amount, parts_count, redundant_parts_count)
    print(f"Payer created payment with {parts_count} parts and {redundant_parts_count} redundant parts")
    
    # 3. Randomly choose parts and forward to payee
    # Select a random subset of the locked parts to simulate network forwarding
    selected_ptlcs = random.sample(ptlcs, parts_count)  # Ensure we have enough parts
    for ptlc in selected_ptlcs:
        payee.receive_ptlcs([ptlc])
        print(f"Forwarded payment part {ptlc.id} to payee")
        if payee.get_received_ptlcs(payment_hash):
            print(f"Payee received enough parts")
            break
        else:
            print(f"Waiting for next part")
    
    # 4. Check if payee has enough parts
    received_ptlcs = payee.get_received_ptlcs(payment_hash)
    if received_ptlcs:
        print(f"Payee received enough parts: {len(received_ptlcs)}")
        
        # 5. Ask payer to reveal these parts' preimages
        # First, index the parts for identification
        payer_nonces = payer.reveal_ptlcs(received_ptlcs)
        print(f"Payer revealed {len(payer_nonces)} nonces")
        
        # 6. Payee verifies these revealed preimages via claim function
        claimed_secrets = payee.claim(received_ptlcs, payer_nonces)
        print("Payment successfully claimed by payee")

        # 7. Payer can extract payment proof from claim
        payment = payer.find_payment(payment_hash)
        payment_proof = None
        for index, claimed_secret in enumerate(claimed_secrets):
            ptlc = received_ptlcs[index]
            payer_nonce_secret = payment.nonce_secrets[ptlc.id]
            secret = claimed_secret - payer_nonce_secret
            if payment_proof is None:
                payment_proof = secret
            if payment_proof != secret:
                raise Exception("Payment proof is not consistent")
                
        print(f"Payment proof: {payment_proof}")
        # 8. Any one with invoice pubkey can verify payment proof
        invoice = payee.find_invoice(payment_hash)
        pubkey = SecretKey(payment_proof).pubkey()
        print(f"Payment proof pubkey: {pubkey.pubkey}")
        print(f"Invoice pubkey: {invoice.pubkey.pubkey}")
        if pubkey.pubkey == invoice.pubkey.pubkey:
            print("Payment proof is verified")
        else:
            raise Exception("Payment proof is not verified")
    else:
        print("Payee didn't receive enough parts to claim payment")

if __name__ == "__main__":
    run_test() 
