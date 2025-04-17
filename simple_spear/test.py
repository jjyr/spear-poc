import hashlib
import uuid
import random
from simple_spear.node import Node

def run_test():
    print("Running simple spear protocol test...")
    
    # 0. Setup two nodes: payer and payee
    payer = Node()
    payee = Node()
    
    # Add some balance to payer
    payer.balance = 1000
    
    # 1. Payee creates invoice
    amount = 100
    payment_hash, _ = payee.new_invoice(amount)
    print(f"Payee created invoice with payment hash: {payment_hash}")
    
    # 2. Payer pays invoice
    parts_count = 5
    redundant_parts_count = 2
    htlcs = payer.pay(payment_hash, amount, parts_count, redundant_parts_count)
    print(f"Payer created payment with {parts_count} parts and {redundant_parts_count} redundant parts")
    
    # 3. Randomly choose parts and forward to payee
    # Select a random subset of the locked parts to simulate network forwarding
    selected_htlcs = random.sample(htlcs, parts_count)  # Ensure we have enough parts
    for htlc in selected_htlcs:
        payee.receive_htlcs([htlc])
        print(f"Forwarded payment part to payee")
        if payee.get_received_htlcs(payment_hash, htlc.set_id):
            print(f"Payee received enough parts")
            break
        else:
            print(f"Waiting for next part")
    
    # 4. Check if payee has enough parts
    received_htlcs = payee.get_received_htlcs(payment_hash, htlcs[0].set_id)
    if received_htlcs:
        print(f"Payee received enough parts: {len(received_htlcs)}")
        
        # 5. Ask payer to reveal these parts' preimages
        # First, index the parts for identification
        payer_preimages = payer.reveal_htlcs(received_htlcs)
        print(f"Payer revealed {len(payer_preimages)} preimages")
        
        # 6. Payee verifies these revealed preimages via claim function
        payee.claim(received_htlcs, payer_preimages)
        print("Payment successfully claimed by payee")
    else:
        print("Payee didn't receive enough parts to claim payment")

if __name__ == "__main__":
    run_test() 
