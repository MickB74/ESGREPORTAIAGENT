import json

# Raw TSV data provided by user
raw_data = """NVIDIA CORPORATION (XNAS:NVDA)	NVDA	NVIDIA CORPORATION	NVIDIA Corporation is a full-stack computing infrastructure company...	NVIDIA Corporation	$4,396,598,822,021.00	no	https://www.nvidia.com/en-us/csr/
MICROSOFT CORPORATION (XNAS:MSFT)	MSFT	MICROSOFT CORPORATION	Microsoft Corporation is a technology company...	Microsoft Corporation	$3,593,331,800,732.00	no	https://www.microsoft.com/en-us/corporate-responsibility/sustainability/progress
APPLE INC. (XNAS:AAPL)	AAPL	APPLE INC.	Apple Inc. designs, manufactures and markets smartphones...	Apple Inc.	$4,108,268,572,462.00	no	https://www.apple.com/environment/
AMAZON.COM, INC. (XNAS:AMZN)	AMZN	AMAZON.COM, INC.	Amazon.com, Inc. provides a range of products...	Amazon.com, Inc.	$2,461,741,545,750.00	no	https://sustainability.aboutamazon.com/
ALPHABET INC. (XNAS:GOOG)	GOOG	ALPHABET INC.	Alphabet Inc. is a holding company...	Alphabet Inc.	$3,774,260,537,720.00	no	https://sustainability.google/
ALPHABET INC. (XNAS:GOOGL)	GOOGL	ALPHABET INC.	Alphabet Inc. is a holding company...	Alphabet Inc.	$3,774,260,537,720.00	no	https://sustainability.google/
Meta Platforms, Inc. (XNAS:META)	META	Meta Platforms, Inc.	Meta Platforms, Inc. builds technology...	Meta Platforms, Inc.	$1,645,173,886,262.00	no	https://sustainability.atmeta.com/
BROADCOM INC. (XNAS:AVGO)	AVGO	BROADCOM INC.	Broadcom Inc. is a global technology firm...	Broadcom Inc.	$1,919,027,035,621.00	no	https://www.broadcom.com/company/corporate-responsibility
BERKSHIRE HATHAWAY INC. (XNYS:BRK.B)	BRK.B	BERKSHIRE HATHAWAY INC.	Berkshire Hathaway Inc. and its subsidiaries...	Berkshire Hathaway Inc.	$1,068,293,319,100.00	no	https://www.brkenergy.com/environmental
TESLA, INC. (XNAS:TSLA)	TSLA	TESLA, INC.	Tesla, Inc. designs, develops, manufactures...	Tesla, Inc.	$1,400,240,909,727.00	no	https://www.tesla.com/impact
JPMORGAN CHASE & CO. (XNYS:JPM)	JPM	JPMORGAN CHASE & CO.	JPMorgan Chase & Co. is a financial holding company...	JPMorgan Chase & Co.	$872,716,620,566.00	yes	https://www.jpmorganchase.com/about/governance/esg
WALMART INC. (XNYS:WMT)	WMT	WALMART INC.	Walmart Inc. is a technology-powered omnichannel retailer...	Walmart Inc.	$920,713,549,564.00	no	https://corporate.walmart.com/purpose
ELI LILLY AND COMPANY (XNYS:LLY)	LLY	ELI LILLY AND COMPANY	Eli Lilly and Company is a medicine company...	Eli Lilly and Company	$954,251,403,722.00	no	https://sustainability.lilly.com/
VISA INC. (XNYS:V)	V	VISA INC.	Visa Inc. is a global payments technology company...	Visa Inc.	$660,926,483,647.00	no	https://corporate.visa.com/en/about-visa/crs.html
ORACLE CORPORATION (XNYS:ORCL)	ORCL	ORACLE CORPORATION	Oracle Corporation offers integrated suites...	Oracle Corporation	$566,880,006,599.00	no	https://www.oracle.com/social-impact/
NETFLIX, INC. (XNAS:NFLX)	NFLX	NETFLIX, INC.	Netflix, Inc. is a provider of entertainment services...	Netflix, Inc.	$429,943,767,816.00	no	https://about.netflix.com/en/sustainability
MASTERCARD INCORPORATED. (XNYS:MA)	MA	MASTERCARD INCORPORATED.	Mastercard Incorporated is a technology company...	Mastercard Incorporated	$505,903,833,124.00	no	https://www.mastercard.us/en-us/vision/corp-responsibility.html
EXXON MOBIL CORPORATION (XNYS:XOM)	XOM	EXXON MOBIL CORPORATION	Exxon Mobil Corporation is an energy provider...	Exxon Mobil Corporation	$504,119,907,960.00	no	https://corporate.exxonmobil.com/sustainability-and-reports/sustainability
COSTCO WHOLESALE CORPORATION (XNAS:COST)	COST	COSTCO WHOLESALE CORPORATION	Costco Wholesale Corporation (Costco) operates...	Costco Wholesale Corporation	$392,671,700,000.00	no	https://www.costco.com/sustainability-introduction.html
THE PROCTER & GAMBLE COMPANY (XNYS:PG)	PG	THE PROCTER & GAMBLE COMPANY	The Procter & Gamble Company is focused on providing...	The Procter & Gamble Company	$328,918,524,243.00	no	https://us.pg.com/environmental-sustainability/
JOHNSON & JOHNSON (XNYS:JNJ)	JNJ	JOHNSON & JOHNSON	Johnson & Johnson and its subsidiaries are engaged...	Johnson & Johnson	$505,976,029,715.00	no	https://www.jnj.com/esg-resources
THE HOME DEPOT, INC. (XNYS:HD)	HD	THE HOME DEPOT, INC.	The Home Depot, Inc. is a home improvement retailer...	The Home Depot, Inc.	$355,855,460,791.00	no	https://corporate.homedepot.com/page/resources-reports
BANK OF AMERICA CORPORATION (XNYS:BAC)	BAC	BANK OF AMERICA CORPORATION	Bank of America Corporation is a bank holding company...	Bank of America Corporation	$398,424,191,788.00	no	https://about.bankofamerica.com/en/making-an-impact/esg-reports
ABBVIE INC. (XNYS:ABBV)	ABBV	ABBVIE INC.	AbbVie Inc. is a global, diversified research-based...	AbbVie Inc.	$395,858,660,768.00	no	https://www.abbvie.com/sustainability/environmental-social-and-governance.html
PALANTIR TECHNOLOGIES INC. (XNAS:PLTR)	PLTR	PALANTIR TECHNOLOGIES INC.	Palantir Technologies Inc. is engaged in building...	Palantir Technologies Inc.	$446,801,093,744.00	no	https://www.palantir.com/climate-pledge/
THE COCA-COLA COMPANY (XNYS:KO)	KO	THE COCA-COLA COMPANY	The Coca-Cola Company is a beverage company...	The Coca-Cola Company	$297,284,200,615.00	no	https://www.coca-colacompany.com/sustainability
UNITEDHEALTH GROUP INCORPORATED (XNYS:UNH)	UNH	UNITEDHEALTH GROUP INCORPORATED	UnitedHealth Group Incorporated is a healthcare company...	UnitedHealth Group Incorporated	$305,023,008,056.00	no	https://www.unitedhealthgroup.com/sustainability/sustainability-at-uhg.html
Philip Morris International Inc. (XNYS:PM)	PM	Philip Morris International Inc.	Philip Morris International Inc. is an international...	Philip Morris International Inc.	$234,974,501,349.00	no	https://www.pmi.com/sustainability
CISCO SYSTEMS, INC. (XNAS:CSCO)	CSCO	CISCO SYSTEMS, INC.	Cisco Systems, Inc. designs and sells a range...	Cisco Systems, Inc.	$313,203,208,116.00	yes	https://www.cisco.com/c/en/us/about/csr.html
T-MOBILE US, INC. (XNAS:TMUS)	TMUS	T-MOBILE US, INC.	T-Mobile US, Inc. is a provider of wireless...	T-Mobile US, Inc.	$218,477,779,028.00	no	https://www.t-mobile.com/responsibility
WELLS FARGO & COMPANY (XNYS:WFC)	WFC	WELLS FARGO & COMPANY	Wells Fargo & Company is a financial services company...	Wells Fargo & Company	$290,647,776,064.00	no	https://www.wellsfargo.com/about/corporate-responsibility/
INTERNATIONAL BUSINESS MACHINES CORPORATION (XNYS:IBM)	IBM	INTERNATIONAL BUSINESS MACHINES CORPORATION	International Business Machines Corporation is a provider...	International Business Machines Corporation	$290,459,637,993.00	no	https://www.ibm.com/solutions/sustainability/environmental
GENERAL ELECTRIC COMPANY (XNYS:GE)	GE	GENERAL ELECTRIC COMPANY	General Electric Company, doing business as GE Aerospace...	General Electric Company	$304,229,179,623.00	no	https://www.geaerospace.com/sustainability
SALESFORCE, INC. (XNYS:CRM)	CRM	SALESFORCE, INC.	Salesforce, Inc. is a provider of customer relationship...	Salesforce, Inc.	$245,821,955,718.00	no	https://www.salesforce.com/company/sustainability/
CHEVRON CORPORATION (XNYS:CVX)	CVX	CHEVRON CORPORATION	Chevron Corporation is an integrated energy company...	Chevron Corporation	$303,477,887,577.00	no	https://www.chevron.com/sustainability
ABBOTT LABORATORIES (XNYS:ABT)	ABT	ABBOTT LABORATORIES	Abbott Laboratories is a global healthcare company...	Abbott Laboratories	$214,368,138,037.00	no	https://www.abbott.com/responsibility/sustainability.html
MORGAN STANLEY (XNYS:MS)	MS	MORGAN STANLEY	Morgan Stanley is a global financial services company...	Morgan Stanley	$286,841,199,028.00	no	https://www.morganstanley.com/about-us/sustainability-at-morgan-stanley
AMERICAN EXPRESS COMPANY (XNYS:AXP)	AXP	AMERICAN EXPRESS COMPANY	American Express Company is a globally integrated...	American Express Company	$265,132,102,414.00	yes	https://www.americanexpress.com/en-us/company/corporate-sustainability/
LINDE PUBLIC LIMITED COMPANY (XNAS:LIN)	LIN	LINDE PUBLIC LIMITED COMPANY	Linde plc is a United Kingdom-based industrial...	Linde plc	$63,989,562,749.00	no	https://www.linde.com/sustainability
ADVANCED MICRO DEVICES, INC. (XSGO:AMD)	AMD	ADVANCED MICRO DEVICES, INC.	Advanced Micro Devices, Inc. is a global semiconductor...	Advanced Micro Devices, Inc.	$360,497,106,705.00	no	https://www.amd.com/en/corporate/corporate-responsibility.html
THE WALT DISNEY COMPANY (XNYS:DIS)	DIS	THE WALT DISNEY COMPANY	The Walt Disney Company is a diversified worldwide...	The Walt Disney Company	$198,988,198,845.00	yes	https://impact.disney.com/
INTUIT INC. (XNAS:INTU)	INTU	INTUIT INC.	Intuit Inc. offers a financial technology platform...	Intuit Inc.	$188,116,009,457.00	no	https://www.intuit.com/company/corporate-responsibility/
SERVICENOW, INC. (XNYS:NOW)	NOW	SERVICENOW, INC.	ServiceNow, Inc. provides an artificial intelligence...	ServiceNow, Inc.	$179,988,037,659.00	no	https://www.servicenow.com/company/global-impact/sustainability.html
THE GOLDMAN SACHS GROUP, INC. (XNYS:GS)	GS	THE GOLDMAN SACHS GROUP, INC.	The Goldman Sachs Group, Inc. is a global financial...	The Goldman Sachs Group, Inc.	$273,243,779,038.00	no	https://www.goldmansachs.com/investor-relations/corporate-governance/sustainability-reporting
MCDONALD'S CORPORATION (XNYS:MCD)	MCD	MCDONALD'S CORPORATION	McDonald's Corporation is a global foodservice retailer...	McDonald's Corporation	$220,561,302,167.00	no	https://corporate.mcdonalds.com/corpmcd/our-purpose-and-impact/impact-strategy-and-reporting/performance-reports.html
AT&T INC. (XNYS:T)	T	AT&T INC.	AT&T Inc. is a holding company...	AT&T Inc.	$172,273,629,591.00	no	https://about.att.com/csr/home.html
MERCK & CO., INC. (XNYS:MRK)	MRK	MERCK & CO., INC.	Merck & Co., Inc. is a global health care company...	Merck & Co., Inc.	$245,745,003,522.00	no	https://www.merck.com/company-overview/esg/
TEXAS INSTRUMENTS INCORPORATED (XNAS:TXN)	TXN	TEXAS INSTRUMENTS INCORPORATED	Texas Instruments Incorporated is a global semiconductor...	Texas Instruments Incorporated	$165,069,484,245.00	no	https://www.ti.com/about-ti/citizenship-community/environmental-sustainability.html
UBER TECHNOLOGIES, INC. (XNYS:UBER)	UBER	UBER TECHNOLOGIES, INC.	Uber Technologies, Inc. operates a technology platform...	Uber Technologies, Inc.	$177,529,800,272.00	no	https://www.uber.com/us/en/about/sustainability/
INTUITIVE SURGICAL, INC. (XNAS:ISRG)	ISRG	INTUITIVE SURGICAL, INC.	Intuitive Surgical, Inc. develops, manufactures...	Intuitive Surgical, Inc.	$194,036,980,103.00	no	https://www.intuitive.com/en-us/about-us/company/esg
RTX CORPORATION (XNYS:RTX)	RTX	RTX CORPORATION	RTX Corporation is an aerospace and defense company...	RTX Corporation	$237,879,765,784.00	no	https://www.rtx.com/our-responsibility/corporate-responsibility
ACCENTURE PUBLIC LIMITED COMPANY (XNYS:ACN)	ACN	ACCENTURE PUBLIC LIMITED COMPANY	Accenture plc is a global professional services company...	Accenture plc	$167,666,924,327.00	no	https://www.accenture.com/us-en/about/corporate-sustainability
BLACKSTONE INC. (XNYS:BX)	BX	BLACKSTONE INC.	Blackstone Inc. is an alternative asset manager...	Blackstone Inc.	$187,986,769,164.00	no	https://www.blackstone.com/our-impact/building-sustainable-businesses/
CATERPILLAR INC. (XNYS:CAT)	CAT	CATERPILLAR INC.	Caterpillar Inc. is a manufacturer of construction...	Caterpillar Inc.	$292,772,710,700.00	no	https://www.caterpillar.com/en/company/sustainability.html
BOOKING HOLDINGS INC. (XNAS:BKNG)	BKNG	BOOKING HOLDINGS INC.	Booking Holdings Inc. is a provider of travel...	Booking Holdings Inc.	$170,184,207,646.00	no	https://www.bookingholdings.com/sustainability/
PEPSICO, INC. (XNAS:PEP)	PEP	PEPSICO, INC.	PepsiCo, Inc. is a global beverage and convenient...	PepsiCo, Inc.	$203,788,344,419.00	no	https://www.pepsico.com/our-impact/sustainability/esg-data-hub
VERIZON COMMUNICATIONS INC. (XNYS:VZ)	VZ	VERIZON COMMUNICATIONS INC.	Verizon Communications Inc. is a holding company...	Verizon Communications Inc.	$169,584,618,647.00	no	https://www.verizon.com/about/responsibility
QUALCOMM INCORPORATED (XNAS:QCOM)	QCOM	QUALCOMM INCORPORATED	Qualcomm Incorporated is engaged in the development...	QUALCOMM Incorporated	$193,775,459,327.00	no	https://www.qualcomm.com/company/corporate-responsibility
BLACKROCK, INC. (XNYS:BLK)	BLK	BLACKROCK, INC.	BlackRock, Inc. is an investment management company...	BlackRock, Inc.	$170,951,462,352.00	no	https://www.blackrock.com/corporate/sustainability
THE CHARLES SCHWAB CORPORATION (XNYS:SCHW)	SCHW	THE CHARLES SCHWAB CORPORATION	The Charles Schwab Corporation is a savings and loan...	The Charles Schwab Corporation	$172,451,644,222.00	no	https://www.aboutschwab.com/citizenship
CITIGROUP INC. (XNYS:C)	C	CITIGROUP INC.	Citigroup Inc. is a global diversified financial...	Citigroup Inc.	$199,936,266,437.00	no	https://www.citigroup.com/global/our-impact/sustainability
THE BOEING COMPANY (XNYS:BA)	BA	THE BOEING COMPANY	The Boeing Company is an aerospace company...	The Boeing Company	$157,170,205,738.00	no	https://www.boeing.com/principles/sustainability
S&P Global Inc. (XNYS:SPGI)	SPGI	S&P Global Inc.	S&P Global Inc. provides essential intelligence...	S&P Global Inc.	$148,771,700,000.00	no	https://investor.spglobal.com/corporate-governance/Impact-and-TCFD-Reports/
THERMO FISHER SCIENTIFIC INCORPORATED (XNYS:TMO)	TMO	THERMO FISHER SCIENTIFIC INCORPORATED	Thermo Fisher Scientific Inc. is engaged in accelerating...	Thermo Fisher Scientific Inc.	$217,497,312,482.00	no	https://www.boeing.com/sustainability#introduction
ADOBE INC. (XNAS:ADBE)	ADBE	ADOBE INC.	Adobe Inc. is a global technology company...	Adobe Inc.	$146,689,959,891.00	no	https://www.adobe.com/corporate-responsibility.html
AMGEN INC. (XNAS:AMGN)	AMGN	AMGEN INC.	Amgen Inc. is a biotechnology company...	Amgen Inc.	$170,902,943,719.00	no	https://www.amgen.com/responsibility
HONEYWELL INTERNATIONAL INCORPORATION (XNAS:HON)	HON	HONEYWELL INTERNATIONAL INCORPORATION	Honeywell International Inc. is an integrated operating...	Honeywell International Inc.	$123,072,848,825.00	no	https://www.honeywell.com/us/en/company/impact-report
BOSTON SCIENTIFIC CORPORATION (XNYS:BSX)	BSX	BOSTON SCIENTIFIC CORPORATION	Boston Scientific Corporation is a global developer...	Boston Scientific Corporation	$136,014,053,500.00	no	https://www.bostonscientific.com/en-US/corporate-social-responsibility.html
THE PROGRESSIVE CORPORATION (XNYS:PGR)	PGR	THE PROGRESSIVE CORPORATION	The Progressive Corporation is an insurance holding...	The Progressive Corporation	$135,106,950,387.00	no	https://www.progressive.com/about/corporate-responsibility/
APPLIED MATERIALS, INC. (XNAS:AMAT)	AMAT	APPLIED MATERIALS, INC.	Applied Materials, Inc. is a materials engineering...	Applied Materials, Inc.	$215,181,094,005.00	no	https://www.appliedmaterials.com/us/en/corporate-responsibility.html
NEXTERA ENERGY, INC. (XNYS:NEE)	NEE	NEXTERA ENERGY, INC.	NextEra Energy, Inc. is an electric power and energy...	NextEra Energy, Inc.	$169,128,674,983.00	no	https://www.investor.nexteraenergy.com/sustainability/sustainability-resources
STRYKER CORPORATION (XNYS:SYK)	SYK	STRYKER CORPORATION	Stryker Corporation is a medical technology company...	Stryker Corporation	$134,984,058,558.00	no	https://www.stryker.com/us/en/about/corporate-responsibility.html
DANAHER CORPORATION (XNYS:DHR)	DHR	DANAHER CORPORATION	Danaher Corporation is a global life sciences...	Danaher Corporation	$164,134,476,340.00	no	https://www.danaher.com/sustainability
PFIZER INC. (XNYS:PFE)	PFE	PFIZER INC.	Pfizer Inc. is a research-based, global biopharmaceutical...	Pfizer Inc.	$146,691,184,662.00	yes	https://www.pfizer.com/about/responsibility/environmental-sustainability
EATON CORPORATION PUBLIC LIMITED COMPANY (XNYS:ETN)	ETN	EATON CORPORATION PUBLIC LIMITED COMPANY	Eaton Corporation plc is an intelligent power...	Eaton Corporation plc	$136,079,818,310.00	no	https://www.eaton.com/us/en-us/company/sustainability.html
UNION PACIFIC CORPORATION (XNYS:UNP)	UNP	UNION PACIFIC CORPORATION	Union Pacific Corporation, through its principal...	Union Pacific Corporation	$140,057,172,423.00	no	https://www.up.com/investors/sustainability
GE VERNOVA INC. (XNYS:GEV)	GEV	GE VERNOVA INC.	GE Vernova Inc. is a global energy company...	GE Vernova Inc.	$191,063,828,992.00	no	https://www.gevernova.com/sustainability
DEERE & COMPANY (XNYS:DE)	DE	DEERE & COMPANY	Deere & Company is engaged in the delivery of...	Deere & Company	$128,660,575,295.00	no	https://www.deere.com/en/our-company/sustainability/
THE TJX COMPANIES, INC. (XNYS:TJX)	TJX	THE TJX COMPANIES, INC.	The TJX Companies, Inc. is an off-price apparel...	The TJX Companies, Inc.	$172,766,457,893.00	no	https://www.tjx.com/responsibility
GILEAD SCIENCES, INC. (XNAS:GILD)	GILD	GILEAD SCIENCES, INC.	Gilead Sciences, Inc. is a biopharmaceutical company...	Gilead Sciences, Inc.	$152,864,058,454.00	no	https://www.gilead.com/purpose/esg
MICRON TECHNOLOGY, INC. (XNAS:MU)	MU	MICRON TECHNOLOGY, INC.	Micron Technology, Inc. provides memory and storage...	Micron Technology, Inc.	$290,857,692,923.00	no	https://www.micron.com/about/sustainability/sustainability-report
PALO ALTO NETWORKS, INC. (XNAS:PANW)	PANW	PALO ALTO NETWORKS, INC.	Palo Alto Networks, Inc. is a global cybersecurity...	Palo Alto Networks, Inc.	$132,680,882,353.00	no	https://www.paloaltonetworks.com/about-us/corporate-responsibility
COMCAST CORPORATION (XNAS:CMCSA)	CMCSA	COMCAST CORPORATION	Comcast Corporation is a global media and technology...	Comcast Corporation	$100,571,475,790.00	no	https://www.cmcsa.com/corporate-responsibility-reporting
ARISTA NETWORKS, INC. (XNYS:ANET)	ANET	ARISTA NETWORKS, INC.	Arista Networks, Inc. is a provider of data-driven...	Arista Networks Inc	$169,235,310,381.00	no	https://www.arista.com/en/company/corporate-responsibility
CROWDSTRIKE HOLDINGS, INC. (XNAS:CRWD)	CRWD	CROWDSTRIKE HOLDINGS, INC.	CrowdStrike Holdings, Inc. is a global cybersecurity...	CrowdStrike Holdings, Inc.	$130,498,691,149.00	no	https://www.crowdstrike.com/en-us/about-us/environmental-social-governance/
LOWE'S COMPANIES, INC. (XNYS:LOW)	LOW	LOWE'S COMPANIES, INC.	Lowe's Companies, Inc. is a home improvement company...	Lowe's Companies, Inc.	$139,160,873,955.00	no	https://corporate.lowes.com/our-responsibilities
LAM RESEARCH CORPORATION (XNAS:LRCX)	LRCX	LAM RESEARCH CORPORATION	Lam Research Corporation is a global supplier...	Lam Research Corporation	$211,904,661,022.00	no	https://www.lamresearch.com/company/esg/
A DONG PAINT JOINT STOCK COMPANY (XSTC:ADP)	ADP	A DONG PAINT JOINT STOCK COMPANY	ADong Paint Joint Stock Company is a Vietnam-based...	Automatic Data Processing, Inc.	$107,053,500,921.00	no	https://www.adp.com/about-adp/corporate-social-responsibility.aspx
KKR & CO. INC. (XNYS:KKR)	KKR	KKR & CO. INC.	KKR & Co. Inc. is a global investment firm...	KKR & Co. Inc.	$127,258,557,280.00	no	https://www.kkr.com/about/sustainability/resource-center
KLA Corporation (XNAS:KLAC)	KLAC	KLA Corporation	KLA Corporation is a supplier of process control...	KLA Corporation	$163,738,463,471.00	no	https://www.kla.com/company/environmental-social-governance
ANALOG DEVICES, INC. (XNAS:ADI)	ADI	ANALOG DEVICES, INC.	Analog Devices, Inc. is a global semiconductor company...	Analog Devices, Inc.	$138,763,054,232.00	no	https://www.analog.com/en/corporate-responsibility.html
AMPHENOL CORPORATION (XNYS:APH)	APH	AMPHENOL CORPORATION	Amphenol Corporation is a designer, manufacturer...	Amphenol Corporation	$170,253,805,467.00	no	https://www.amphenol.com/sustainability
CONOCOPHILLIPS (XNYS:COP)	COP	CONOCOPHILLIPS	ConocoPhillips is an exploration and production...	ConocoPhillips	$119,506,189,938.00	no	https://www.conocophillips.com/sustainability/
VERTEX PHARMACEUTICALS INCORPORATED (XNAS:VRTX)	VRTX	VERTEX PHARMACEUTICALS INCORPORATED	Vertex Pharmaceuticals Incorporated is a global...	Vertex Pharmaceuticals Incorporated	$113,140,778,032.00	no	https://www.vrtx.com/en-us/responsibility/
Chubb Ltd (XNYS:CB)	CB	Chubb Ltd	Chubb Limited is a Switzerland-based holding company...	Chubb Limited	$120,418,708,705.00	no	https://about.chubb.com/citizenship.html
MEDTRONIC PUBLIC LIMITED COMPANY (XNYS:MDT)	MDT	MEDTRONIC PUBLIC LIMITED COMPANY	Medtronic Public Limited Company is an Ireland-based...	Medtronic plc	$127,880,896,500.00	no	https://www.medtronic.com/us-en/about/esg.html
NIKE, INC. (XNYS:NKE)	NKE	NIKE, INC.	NIKE, Inc. is engaged in the designing...	NIKE, Inc.	$100,133,332,582.00	no	https://about.nike.com/en/impact
LOCKHEED MARTIN CORPORATION (XNYS:LMT)	LMT	LOCKHEED MARTIN CORPORATION	Lockheed Martin Corporation is a global aerospace...	Lockheed Martin Corporation	$109,886,188,393.00	no	https://www.lockheedmartin.com/en-us/who-we-are/sustainability.html
STARBUCKS CORPORATION (XNAS:SBUX)	SBUX	STARBUCKS CORPORATION	Starbucks Corporations is a roaster, marketer...	Starbucks Corporation	$96,357,850,000.00	no	https://www.starbucks.com/responsibility/
MARSH & MCLENNAN COMPANIES, INC. (XNYS:MMC)	MMC	MARSH & MCLENNAN COMPANIES, INC.	Marsh & McLennan Companies, Inc. is a professional...	Marsh & McLennan Companies, Inc.	$89,883,714,910.00	no	https://www.marshmclennan.com/about/esg.html
INTERCONTINENTAL EXCHANGE, INC. (XNYS:ICE)	ICE	INTERCONTINENTAL EXCHANGE, INC.	Intercontinental Exchange, Inc. provides financial...	Intercontinental Exchange, Inc.	$92,996,116,830.00	no	https://www.ice.com/about/corporate-responsibility
AMERICAN TOWER CORPORATION (XNYS:AMT)	AMT	AMERICAN TOWER CORPORATION	American Tower Corporation is a real estate investment...	American Tower Corporation	$85,066,921,829.00	no	https://www.americantower.com/sustainability/
PROLOGIS, INC. (XNYS:PLD)	PLD	PROLOGIS, INC.	Prologis, Inc. is a fully integrated real estate company...	Prologis, Inc.	$121,272,834,084.00	no	https://www.prologis.com/esg
DOORDASH, INC. (XNAS:DASH)	DASH	DOORDASH, INC.	DoorDash, Inc. is engaged in providing services...	DoorDash, Inc.	$96,767,785,061.00	no	https://ir.doordash.com/governance/ESG-Resources/default.aspx
THE SOUTHERN COMPANY (XNYS:SO)	SO	THE SOUTHERN COMPANY	The Southern Company is an energy provider...	The Southern Company	$93,296,545,616.00	no	https://www.southerncompany.com/sustainability.html
Altria Group, Inc. (XNYS:MO)	MO	Altria Group, Inc.	Altria Group, Inc. operates a portfolio of tobacco...	Altria Group, Inc.	$98,571,563,169.00	no	https://www.altria.com/responsibility
WELLTOWER INC. (XNYS:WELL)	WELL	WELLTOWER INC.	Welltower Inc. is a residential wellness...	Welltower Inc.	$126,950,090,997.00	no	https://welltower.com/sustainability-overview/
CME GROUP INC. (XNAS:CME)	CME	CME GROUP INC.	CME Group Inc. provides a derivatives marketplace...	CME Group Inc.	$98,228,316,382.00	no	https://www.cmegroup.com/company/corporate-citizenship/esg.html
INTEL CORPORATION (XNAS:INTC)	INTC	INTEL CORPORATION	Intel Corporation is a global designer and manufacturer...	Intel Corporation	$188,462,691,993.00	no	https://www.intel.com/content/www/us/en/corporate-responsibility/corporate-responsibility.html
CONSTELLATION ENERGY CORPORATION. (XNAS:CEG)	CEG	CONSTELLATION ENERGY CORPORATION.	Constellation Energy Corporation is a producer...	Constellation Energy Corporation	$118,233,033,766.00	no	https://www.constellationenergy.com/our-impact/resources/constellation-sustainability-report.html
Trane Technologies plc (XNYS:TT)	TT	Trane Technologies plc	Trane Technologies PLC is a global climate innovator...	Trane Technologies plc	$89,445,078,902.00	no	https://www.tranetechnologies.com/en/index/sustainability.html
FISERV, INC. (XNYS:FI)	FI	FISERV, INC.	Fiserv, Inc. is a global provider...	Fiserv, Inc.	$98,623,171,940.00	no	https://investors.fiserv.com/esg"""

company_map = {}

import re

for line in raw_data.split('\n'):
    if not line.strip(): continue
    
    # Try splitting by tab first
    parts = line.split('\t')
    
    # If tabs didn't work, try splitting by 2+ spaces
    if len(parts) < 5:
        parts = re.split(r'\s{2,}', line.strip())
        
    if len(parts) >= 5:
        try:
            # Layout seems to be:
            # ... | Company Name | Market Cap | MVP? | Website
            # Index from right is safer
            website = parts[-1].strip()
            # mvp = parts[-2]
            # cap = parts[-3]
            name = parts[-4].strip()
            
            # Ticker is usually near the start
            # "1 NVIDIA CORPORATION (XNAS:NVDA)..."
            # It's harder to get ticker reliably with regex split if columns merge,
            # but Company Name and Website are the most important.
            
            # Let's try to get ticker from the second column if possible, but Name is priority.
            ticker = ""
            if len(parts) > 6:
                 ticker = parts[1].strip()

            if website.startswith('http') and len(name) < 100:
                # Store by name (lowercase)
                company_map[name.lower()] = website
                
                # Store by ticker if it looks like a ticker (short, upper)
                if len(ticker) < 10 and ticker.isupper():
                    company_map[ticker.lower()] = website

                # Clean name: "NVIDIA Corporation" -> "NVIDIA"
                clean_name = name.replace("Corporation", "").replace("Inc.", "").replace("Company", "").replace("plc", "").replace("Group", "").replace("Incorporated", "").replace("Limited", "").strip()
                company_map[clean_name.lower()] = website
        except Exception as e:
            print(f"Error parsing line: {line[:30]}... {e}")

# Save to json within the app structure
with open("company_map.json", "w") as f:
    json.dump(company_map, f, indent=2)

print(f"Created company_map.json with {len(company_map)} entries.")
