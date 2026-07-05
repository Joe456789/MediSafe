import requests

def fetch_openfda_data(ingredient: str) -> str:
    """Fetches FDA enforcement and safety warnings for a given medical ingredient."""
    url = f"https://api.fda.gov/drug/enforcement.json?search=product_description:\"{ingredient}\"&limit=3"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if not results:
                return "No FDA recalls or enforcement reports found."
            output = []
            for item in results:
                output.append(f"- Reason: {item.get('reason_for_recall', 'N/A')}\n  Status: {item.get('status', 'N/A')}")
            return "\n".join(output)
        return "No significant FDA enforcement data found or API error."
    except Exception as e:
        return f"Error fetching FDA data: {str(e)}"

def fetch_pubmed_abstracts(ingredient: str) -> str:
    """Fetches recent medical literature abstracts from PubMed regarding side effects."""
    search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={ingredient}+side+effects&retmode=json&retmax=2"
    try:
        search_res = requests.get(search_url).json()
        id_list = search_res.get('esearchresult', {}).get('idlist', [])
        if not id_list:
            return "No recent side effect studies found on PubMed."
        
        ids = ",".join(id_list)
        summary_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={ids}&retmode=json"
        summary_res = requests.get(summary_url).json()
        
        output = []
        for uid in id_list:
            title = summary_res.get('result', {}).get(uid, {}).get('title', 'Unknown Title')
            output.append(f"- Title: {title}")
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching PubMed data: {str(e)}"

def fetch_clinical_trials(ingredient: str) -> str:
    """Fetches currently active clinical trials for the ingredient from ClinicalTrials.gov API v2."""
    url = f"https://clinicaltrials.gov/api/v2/studies?query.term={ingredient}&filter.overallStatus=RECRUITING&pageSize=2"
    try:
        response = requests.get(url, headers={'Accept': 'application/json'})
        if response.status_code == 200:
            studies = response.json().get('studies', [])
            if not studies:
                return "No active clinical trials found for this ingredient."
            
            output = []
            for study in studies:
                protocol = study.get('protocolSection', {})
                identificationModule = protocol.get('identificationModule', {})
                title = identificationModule.get('briefTitle', 'No title')
                output.append(f"- Trial: {title}")
            return "\n".join(output)
        return "No clinical trial data found."
    except Exception as e:
        return f"Error fetching Clinical Trials data: {str(e)}"
