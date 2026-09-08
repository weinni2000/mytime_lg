Adds a "Detailed Digitize" button next to "Digitize document" on vendor bills.
It sends the attached PDF to ChatGPT and creates one invoice line per line item
found on the document (name, product description, quantity and price).

If the company is marked as Kleinstunternehmer, every extracted price is
multiplied by 1.2 to account for non-deductible input VAT.
