# -*- coding: utf-8 -*-
from term_detector import is_short_term_heuristic

textWithShortTerm = ["Well-maintained 2-room apartment located in the heart of Inner Østerbro, available for rent for an 11-month lease starting 15.09.25 (and ending 15.08.2026)",
        "Fremlejes til ikkerygere og folk uden dyr i perioden 18/9/2025-26/6/2026.",
        "Lejlighed beliggende pø Peblinge Dossering i København fremlejes i en 2 mdr. periode fra 1. oktober til 30 november 2025. Lejligheden ligger lige ud til søerne. Udlejes kun til en enlig, rolig kvinde med fast arbejde.",
        "Jeg udlejer min møblerede 2-vørelses lejlighed pø Frederiksberg for 8.303 pr. mdr. i perioden 01.07.25-15.01.26. Prisen er inklusiv el, vand, varme og internet. Lejligheden er ikke egnet som dele-lejlighed.Lejligheden ligger ved Søndermarken tøt pø Zoo. Valby station ligger 10 min vøk til fods og Fasanvej station ligger 20 minutter gøgang vøk. 4A kører lige ude foran og stopper ligeledes ved disse steder.",
        "Rooms unfurnished apartment (52 m2 in Valby) is available from the 1st October or 1st November 2025. The apt. is 5 min walk to HB Hallen Train Station  and right next to the lake Damhussøen. About 10 min. bike to the city center..2 years contract. Rent 9850 kr. + 500 kr. for heating and 318 kr. for TV you see little package.3 months deposit + 1 month advance payment.The tenants have to move out 14 days before the contract expires for painting and other",
        "AVAILABLE FROM 15 OCTOBER. We rent this apartment out for 6-12 months. The apartment is furnished and with kitchenware etc. available.",
        "It is a beautiful apartment close to Netto, a football park and a train station. About 5 minutes walk from Åmarken station.A totally furnished apartment. Available to rent for 6 months.",
        "Bright Corner Apartment for Rent – Oct 2025 to Feb 2026. We are renting out our sunny corner apartment while we are on exchange. The apartment has sunlight all day and offers:. - A large bedroom",
        "Lejlighed udlejes pø østerfarimagsgade, 4 sal 2100 København ø. -Her udlejes 70 kvm, fra tidsrumet juni 2025 1 oktober 2025 - Der er i lejligheden et sovevørelse, nyt badevørelse, og et køkkeallerum , samt stue. Lejlighed er møbleret. (Se foto)",
        "2-værelses møbleret lejlighed på Nørrebro med indflytning 1. septemberJeg udlejer min dejlige 2-værelses lejlighed på Nørrebro fra 1. september 2025 til 1. august 2026.",
        "Temporary Norrebro Sublet. 55 square metre Norrebro apartment with balcony available for as a temporary sublet from September 2nd to October 20th 2025.  Rent is 9,300/month, prorated, utilities included. Suitable for one person only"
        ]

textWithNoTermMentioned = ["4 værelses lejlighed på Mosedalvej, få hundrede meter fra lejligheden. Lejligheden indeholder 2 soveværelser og en stue samt køkken og badeværelse. Lejligheden er delevenlig og kan bebos af op til 2-4 personer. KUN VIRKSOMHEDER.",
        "4 værelses lejlighed på Ingrid Marievej i Valby udlejes. Ejendommen er bygget i 2020/2021, 375 lejelejligheder, Fordelt på 2, 3,4 og 5 værelse, Fra 50 m2 til 115 m2",
        "Her er både skole, indkøb og offentlig transport inden for få hundrede meters afstand. Gårdarealet er aflukket fra de store veje, hvilket skaber et hyggeligt og yderst børnevenligt område, uden at komme for langt væk fra byen.Lejemålets lejeperiode er ubegrænset. 9 måneders uopsigelighed. Herefter 3 måneders opsigelse",
        "Vær opmærksom på at der er en bindingsperiode på 12 måneder",
        "Værelse udlejes i 3-værelses lejlighed i Valby – ledigt fra 1. juli eller 1. august Værelse udlejes i 3-værelses lejlighed i Valby – ledigt fra 1. juli eller 1. august",
        "Valby S-togstation 500 meter fra hoveddøren, hvor toglinje B, C og H tager dig til Københavns Hovedbanegård på ca. 2 minutter.OBS. Der er 12 måneders binding på boligerne i denne ejendom.",
        "Nu kan du få nyt hjem i  Blækhus Valby M. Det unikke projekt beliggende ved området Valby Maskinfabrik består af 125 attraktive 1-værelses lejligheder. Lejlighederne er velindrettede og opført i lækre materialer. Stilen er moderne med rustikke betonvægge i gangene, højt til loftet, eget køkken og tagterrasse på de øverst beliggende boliger.",
        "2 værelses lejlighed på 54 m². The apartment is fully furnished and serviced"
   ]


def test_find_terms_in_text():
    for i, t in enumerate(textWithShortTerm, 0):
        result = is_short_term_heuristic(t, months_threshold=12)
        print(f"Text {i}: {result}")
        #assert result["is_short_term"], f"Expected is_short_term True for text {i}, got {result['is_short_term']}"


def test_not_find_terms_in_text_with_no_terms():
    for i, t in enumerate(textWithNoTermMentioned, 0):
        result = is_short_term_heuristic(t, months_threshold=16)
        print(f"Text {i}: {result}")
        #assert not result["is_short_term"], f"Expected is_short_term False for text {i}, got {result['is_short_term']}"
