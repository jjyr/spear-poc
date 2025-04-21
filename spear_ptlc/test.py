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
    
    # 3. Randomly choose parts from payer and forward to payee
    # Select a random subset of the ptlc part to simulate network forwarding
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
    if not received_ptlcs:
        print(f"Payee didn't receive enough parts")
        return

    print(f"Payee received enough parts: {len(received_ptlcs)}")
        
    # 5. Ask payer to reveal these ptlc's hop secrets sum
    # payer should ensure that amount of revealed secrets is equal to invoice amount
    payer_secrets = payer.reveal_ptlcs(received_ptlcs)
    print(f"Payer revealed {len(payer_secrets)} secrets")
    
    # 6. Payee verifies these revealed secrets via claim function
    claim_secrets = payee.claim(received_ptlcs, payer_secrets)
    print("Payment successfully claimed by payee")

    # 7. Payer can extract payment proof from claim
    payment = payer.find_payment(payment_hash)
    payment_proof = None
    for index, claim_secret in enumerate(claim_secrets):
        ptlc = received_ptlcs[index]
        payer_hop_secret = payment.hop_secrets[ptlc.id]
        secret = claim_secret - payer_hop_secret
        if payment_proof is None:
            payment_proof = secret
        if payment_proof != secret:
            raise Exception("Payment proof is not consistent")
            
    print(f"Payment proof: {payment_proof}")

    # 8. Anyone with invoice pubkey can verify payment proof
    invoice = payee.find_invoice(payment_hash)
    pubkey = SecretKey(payment_proof).pubkey()
    print(f"Payment proof pubkey: {pubkey.pubkey}")
    print(f"Invoice pubkey: {invoice.pubkey.pubkey}")
    if pubkey.pubkey == invoice.pubkey.pubkey:
        print("Payment proof is verified")
    else:
        raise Exception("Payment proof is not verified")

if __name__ == "__main__":
    run_test() 
