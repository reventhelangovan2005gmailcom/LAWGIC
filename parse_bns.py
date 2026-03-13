import re
import pandas as pd

def parse_bns_text(input_file, output_csv):
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # --- 1. Clean the Noise ---
    # Remove page headers, footers, and government publication metadata
    noise_patterns = [
        r"THE GAZETTE OF INDIA EXTRAORDINARY",
        r"PART II — Section 1",
        r"PUBLISHED BY AUTHORITY",
        r"MINISTRY OF LAW AND JUSTICE",
        r"\[Part II",
        r"No\. \d+\] NEW DELHI.*",
        r"CG-DL-E.*",
        r"Sec\. 1\]",
        r"_+",  # Underscores used for lines
    ]
    
    for pattern in noise_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # --- 2. Extract Sections using Regex ---
    # Logic: Look for a number at the start of a line/sentence followed by a dot (e.g., "103. ")
    # We capture everything until the next number starts.
    section_pattern = re.compile(r'(\n\d{1,3}\.)\s+(.*?)(?=\n\d{1,3}\.|\Z)', re.DOTALL)
    
    matches = section_pattern.findall(text)
    
    structured_data = []

    for match in matches:
        sec_num_raw = match[0].strip().replace(".", "") # Get '103'
        content = match[1].strip()
        
        # Clean up newlines within the content
        content = " ".join(content.split())
        
        # Identify title (usually the first few words or bolded in original text)
        # We will use the first sentence as a rough description
        
        section_title = f"BNS Section {sec_num_raw}"
        
        # Simple logic to add dummy precedents so the app doesn't crash
        # (Since raw text doesn't contain case law)
        pos_prec = "Refer to BNS 2023 Commentary for latest rulings."
        neg_prec = "No contradictory rulings recorded in this dataset."

        structured_data.append({
            'section': section_title,
            'description': content,
            'pos_precedent': pos_prec,
            'neg_precedent': neg_prec
        })

    # --- 3. Save to CSV ---
    if structured_data:
        df = pd.DataFrame(structured_data)
        df.to_csv(output_csv, index=False)
        print(f"Successfully extracted {len(df)} sections into '{output_csv}'")
    else:
        print("No sections found. Please check the raw text formatting.")

if __name__ == "__main__":
    # Run the parser
    parse_bns_text('raw_bns.txt', 'bns_laws.csv')