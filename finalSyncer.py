import requests
import json
from zeep import Client
from lxml import etree

V2_URL = "https://api.rescuegroups.org/http/v2.json"
PETPOINT_URL = "http://ws.petango.com/webservices/wsAdoption.asmx?wsdl"

RGUSER = os.environ["RGUSER"]
RGPASSWORD = os.environ["RGPASSWORD"]
RGACCNUM = os.environ["RGACCNUM"]
PPAUTHKEY = os.environ["PPAUTHKEY"]
RGAUTH = os.environ["RGAUTH"]

client=  Client(PETPOINT_URL)

#Gain token access to RescueGroups through the V2 API
def login():
    loginData = {"username":RGUSER,"password":RGPASSWORD,"accountNumber":RGACCNUM,"action":"login"}
    headers={"Content-Type": "application/vnd.api+json"}
    response = requests.post(V2_URL,headers=headers,json=loginData)
    responseJson=json.loads(response.text)
    return responseJson["data"]["token"], responseJson["data"]["tokenHash"]

token,tokenHash=login()

def gatherDicts():
    results= client.service.AdoptableSearch(authkey=PPAUTHKEY,
    speciesID="",sex="",ageGroup="",location="",site="",onHold="",orderBy="",primaryBreed="",
    secondaryBreed="",specialNeeds="",noDogs="",noCats="",noKids="",stageID="")
    ppData=dict()
    rgData=dict()
    #Petpoint pull
    for i in range(len(results)-1):
        #updates like rescueID: [name, internalID]
        if (results[i]["_value_1"].find(".//ARN").text != None):
            ppData.update({results[i]["_value_1"].find(".//ARN").text : [results[i]["_value_1"].find(".//Name").text, results[i]["_value_1"].find(".//ID").text]})
    #RescueGroups pull
    pageNum=1
    while True:
        rescueGroupsAuth=RGAUTH
        rescueGroups_url="https://api.rescuegroups.org/v5/public/orgs/1703/animals/search/available/?limit=250&page="+str(pageNum)
        headers={"Authorization": rescueGroupsAuth, "Content-Type": "application/vnd.api+json"}
    
        response=requests.get(rescueGroups_url,headers=headers)
        data=response.json()

        for i in data["data"]:
            if "rescueId" in i["attributes"]:
                #updates like rescueID: [name, internalID]
                rgData.update({i["attributes"]["rescueId"]:[i["attributes"]["name"],i["id"]]})
            else:
                print(i["attributes"]["name"]+" lacks a rescueID")
        if (pageNum>=data["meta"]["pages"]):
            break
        else:
            pageNum+=1
    return ppData,rgData

def createAnimal(data):

    headers={
    "Content-Type": "application/vnd.api+json"
    }

    vals={ "animalStatusID": "18","animalBirthdateExact": "No","animalAdoptionPending": "No",
          "animalCourtesy": "No","animalHighlightOrder": 10,"animalLocationPublic": "Yes",
          "animalSponsorable": "No","animalExportAccounts": ["3579","18975"]}
    vals.update(data)
    payload={
    "token": token,
    "tokenHash": tokenHash,
    "objectType": "animals",
    "objectAction": "add",
    "values": [vals]
    }   
    response = requests.post(V2_URL,json=payload,headers=headers)
    print(json.dumps(response.json(), indent=2))


def getPPAdoptableDetails(id):
    results= client.service.AdoptableDetails(
    authkey=PPAUTHKEY,
    animalID=id
    )
    dataToEdit={"animalID": id,"animalAllowExport":"Yes","animalExportAccounts": ["3579","18975"]}
    #basic stuff that can be copied over
    dataToEdit.update({"animalName":results.find(".//AnimalName").text})
    dataToEdit.update({"animalSex":results.find(".//Sex").text})
    dataToEdit.update({"animalSpecies":results.find(".//Species").text})
    dataToEdit.update({"animalSpeciesID":results.find(".//Species").text})
    dataToEdit.update({"animalAltered":results.find(".//Altered").text})
    dataToEdit.update({"animalGeneralAge":results.find(".//AgeGroup").text})
    dataToEdit.update({"animalRescueID":results.find(".//ARN").text})
    #for some reason, this is by default set to "space"
    dataToEdit.update({"animalKillReason":""})
    #Housetrained
    if (results.find(".//Housetrained").text !="Unknown"):
        dataToEdit.update({"animalHousetrained":results.find(".//Housetrained").text})
    elif (results.find(".//AgeGroup").text=="Young" or results.find(".//AgeGroup").text == "Adult"):
        dataToEdit.update({"animalHousetrained":"Yes"})
    if (results.find(".//ChipNumber").text !=None):
        dataToEdit.update({"animalMicrochipNumber":results.find(".//ChipNumber").text})
    #Coat length
    pBreed=results.find(".//PrimaryBreed").text
    if (results.find(".//Species").text=="Cat"):
        if ("short" in pBreed.lower()):
            dataToEdit.update({"animalCoatLength":"Short"})
        elif ("medium" in pBreed.lower()):
            dataToEdit.update({"animalCoatLength":"Medium"})
        elif ("long" in pBreed.lower()):
            dataToEdit.update({"animalCoatLength":"Long"})
    else:
    #assumes dogs will have short coat length
        dataToEdit.update({"animalCoatLength":"Short"})
    #Size data
    petSize=results.find(".//Size").text
    sizes={"S":"Small","M":"Medium","L":"Large","XL":"X-Large"}
    for size in sizes.keys():
        if (petSize==size):
            dataToEdit.update({"animalGeneralSizePotential":sizes[size]})
    #DateOfBirth data
    dob=results.find(".//DateOfBirth").text
    #petpoint format: YYYY-MM-DD, rescuegroups v2 format: MM/DD/YYYY
    newDob=dob[5]+dob[6]+"/"+dob[8]+dob[9]+"/"+dob[0]+dob[1]+dob[2]+dob[3]
    dataToEdit.update({"animalBirthdate":newDob})
    dataToEdit.update({"animalBirthdateExact":"No"})
    #Declawed data
    declawed=results.find(".//Declawed").text
    if (declawed==None or declawed=="No"):
        dataToEdit.update({"animalDeclawed":"No"})
    elif declawed != "No":
        dataToEdit.update({"animalDeclawed":"Yes"})
    #Special needs data
    specialNeeds=results.find(".//SpecialNeeds").text
    if (specialNeeds==None or specialNeeds=="No"):
        dataToEdit.update({"animalSpecialneeds":"No"})
    elif specialNeeds != "No":
        dataToEdit.update({"animalSpecialneeds":"Yes"})
    #keyFindingFuncs
    catPatterns={"Bicolor": "12", "Calico": "9", "Cow": "15", "Solid": "11", "Spotted": "7", "Tabby": "8", "Tortie": "10","Tortoiseshell": "10", "Tricolor": "13", "Tuxedo": "14"}
    dogPatterns={"Bicolor": "5", "Brindle": "2", "Merle": "3", "Patches": "4", "Spots": "1", "Tricolor": "6"}
    dataToEdit.update({"animalPatternID":findRGKey(results,catPatterns,dogPatterns,"ColorPattern")})

    catColors={"Black": "1", "Black (Mostly)": "5", "Black and White": "6", "Blue": "52", "Blue (Mostly)": "64", "Brown": "7", "Brown (Mostly)": "8", "Brown Tabby": "9", "Calico or Dilute Calico": "10", "Chocolate": "62", "Chocolate (Mostly)": "63", "Cream": "2", "Cream (Mostly)": "3", "Cream and White": "615", "Fawn": "54", "Fawn (Mostly)": "66", "Fawn Tabby": "19","Grey": "11", "Gray": "11", "Gray (Mostly)": "12", "Gray and White": "616", "Gray, Blue or Silver Tabby": "13", "Ivory": "60", "Ivory (Mostly)": "61", "Orange": "14", "Orange (Mostly)": "15", "Orange and White": "617", "Red": "53", "Red (Mostly)": "65", "Red Tabby": "16", "Spotted Tabby/Leopard Spotted": "4", "Tan": "17", "Tan (Mostly)": "18", "Tortoiseshell": "20", "Tuxedo": "67", "White": "21", "White (Mostly)": "22"}
    dogColors={"Black": "23", "Black with Brown, Red, Golden, Orange or Chestnut": "41", "Black with Gray or Silver": "42", "Black with Tan, Yellow or Fawn": "24", "Black with White": "25", "Blue/Silver/Salt & Pepper": "44", "Brindle": "26", "Brindle with White": "27", "Brown/Chocolate": "28", "Brown/Chocolate with Black": "29", "Brown/Chocolate with Tan": "43", "Brown/Chocolate with White": "30", "Fawn": "35", "Golden/Chestnut": "31", "Gray": "59","Grey": "59", "Gray/Silver/Salt & Pepper with Black": "46", "Gray/Silver/Salt & Pepper with White": "45", "Lemon with White": "620", "Liver with White": "619", "Merle": "47", "Orange": "56", "Red": "55", "Red/Golden/Orange/Chestnut with Black": "32", "Red/Golden/Orange/Chestnut with White": "33", "Sable": "618", "Silver & Tan (Yorkie colors)": "34", "Tan": "57", "Tan/Yellow/Fawn with Black": "48", "Tan/Yellow/Fawn with White": "36", "Tricolor (Tan/Brown & Black & White)": "37", "White": "38", "White with Black": "39", "White with Brown or Chocolate": "40", "White with Gray or Silver": "51", "White with Red, Golden, Orange or Chestnut": "50", "White with Tan, Yellow or Fawn": "49", "Yellow": "58"}
    dataToEdit.update({"animalColorID":findRGKey(results,catColors,dogColors,"PrimaryColor")})

    catBreeds={"Abyssinian": "1", "American Curl": "2", "American Shorthair": "3", "American Wirehair": "4", "Angora": "5", "Applehead Siamese": "6", "Balinese": "7", "Bengal": "8", "Birman": "9", "Bobtail": "10", "Bombay": "11", "Brazilian Shorthair": "595", "British Shorthair": "12", "Burmese": "13", "Burmilla": "14", "Calico": "15", "Canadian Hairless": "16", "Chanilly/Tiffany": "596", "Chartreux": "597", "Chausie": "17", "Chinchilla": "19", "Colorpoint Shorthair": "598", "Cornish Rex": "20", "Cymric": "21", "Devon Rex": "22", "Dilute Calico": "426", "Dilute Tortoiseshell": "23", "Domestic Longhair":"24","Domestic Long Hair": "24","Domestic Mediumhair":"29", "Domestic Medium Hair": "29","Domestic Shorthair":"35", "Domestic Short Hair": "35", "Egyptian Mau": "42", "European Burmese": "735", "European Shorthair": "599", "Exotic Shorthair": "43", "Extra-Toes Cat (Hemingway Polydactyl)": "437", "German Rex": "600", "Havana": "44", "Himalayan": "45", "Japanese Bobtail": "46", "Javanese": "438", "Korat": "47", "LaPerm": "439", "Maine Coon": "48", "Malayan": "851", "Manx": "49", "Munchkin": "440", "Nebelung": "441", "Norwegian Forest Cat": "50", "Ocicat": "51", "Oriental Long Hair": "442", "Oriental Short Hair": "443", "Oriental Tabby": "52", "Persian": "53", "Pixie-Bob": "54", "Ragamuffin": "444", "Ragdoll": "55", "Rex": "852", "Russian Blue": "56", "Savannah": "853", "Scottish Fold": "57", "Scottish Straight": "975", "Selkirk Rex": "58", "Siamese": "59", "Siberian": "446", "Singapura": "447", "Snowshoe": "60", "Somali": "61", "Sphynx (hairless cat)": "62", "Tabby": "63", "Tiffany": "855", "Tiger": "68", "Tonkinese": "69", "Torbie": "70", "Tortoiseshell": "71", "Turkish Angora": "450", "Turkish Van": "72", "Tuxedo": "73"}
    dogBreeds={"Affenpinscher": "74", "Afghan Hound": "75", "Airedale Terrier": "76", "Akbash": "77", "Akita": "78", "Alaskan Klee Kai": "893", "Alaskan Malamute": "79", "American Bulldog": "80", "American Eskimo Dog": "81", "American Foxhound": "728", "American Hairless Terrier": "958", "American Pit Bull Terrier": "729","Terrier, American Pit Bull": "729", "American ": "82","Terrier, American Staffordshire":"82", "American Water Spaniel": "325", "Anatolian Karabash Dog": "730", "Anatolian Shepherd": "83", "Appenzell Mountain Dog": "327", "Argentinian Mastiff": "602", "Australian Cattle Dog/Blue Heeler": "84", "Australian Kelpie": "85", "Australian Shepherd": "86", "Australian Terrier": "87", "Basenji": "88", "Basset Griffon Vendeen": "731", "Basset Hound": "89", "Beagle": "90", "Bearded Collie": "91", "Beauceron": "92", "Bedlington Terrier": "329", "Belgian Griffon": "603", "Belgian Shepherd Dog Sheepdog": "93", "Belgian Shepherd Laekenois": "330", "Belgian Shepherd Malinois": "331", "Belgian Shepherd Tervuren": "332", "Bernese Mountain Dog": "94", "Bichon Frise": "95", "Biewer": "952", "Black and Tan Coonhound": "96", "Black Labrador Retriever": "333", "Black Mouth Cur": "97", "Black Russian Terrier": "334", "Bloodhound": "98", "Blue Lacy": "751", "Bluetick Coonhound": "335", "Bobtail": "604", "Boerboel Mastiff": "954", "Bolognese": "732", "Bordeaux": "100", "Border Collie": "99", "Border Terrier": "336", "Borzoi": "101", "Boston Terrier": "102", "Bouvier des Flandres": "103", "Boxer": "104", "Boykin Spaniel": "338", "Brazilian Mastiff": "605", "Briard": "105", "Brittany": "106", "Brussels Griffon": "107", "Bull Terrier": "108", "Bulldog": "109", "Bullmastiff": "110", "Cairn Terrier": "111", "Canaan Dog": "339", "Cane Corso Mastiff": "112","Cane Corso": "112", "Cardigan Welsh Corgi": "584", "Carolina Dog": "113", "Catahoula Leopard Dog": "114", "Cattle Dog": "115", "Caucasian Sheepdog (Caucasian Ovtcharka)": "340", "Cavalier King Charles Spaniel": "116", "Chesapeake Bay Retriever": "117", "Chihuahua": "118","Chihuahua, Long Coat": "118","Chihuahua, Short Coat": "118", "Chinese Crested-Hairless": "119", "Chinese Crested-Powder Puff": "606", "Chinese Foo Dog": "342", "Chinese Shar-Pei": "120", "Chinook": "343", "Chocolate Labrador Retriever": "344", "Chow Chow": "121", "Cirneco dellEtna": "752", "Clumber Spaniel": "345", "Cockapoo": "122", "Cocker Spaniel": "123", "Collie": "124", "Coonhound": "125", "Corgi": "126", "Coton de Tulear": "346", "Curly-Coated Retriever": "347", "Dachshund": "127", "Dalmatian": "128", "Dandie Dinmont Terrier": "129", "Danish Broholmer": "960", "Deerhound": "733", "Doberman Pinscher": "130", "Dogo Argentino": "348", "Dogue de Bordeaux": "349", "Dutch Shepherd": "131", "Elkhound": "607", "English Bulldog": "350", "English Cocker Spaniel": "351", "English Coonhound": "352", "English Foxhound": "734", "English Mastiff": "608", "English Pointer": "132", "English Setter": "133", "English Sheepdog": "609", "English Shepherd": "134", "English Springer Spaniel": "135", "English Toy Spaniel": "136", "Entlebucher": "353", "Eskimo Dog": "137", "Eskimo Spitz": "610", "Eurasier": "354", "Feist": "611", "Field Spaniel": "355", "Fila Brasileiro": "356", "Finnish Lapphund": "357", "Finnish Spitz": "138", "Flat-coated Retriever": "139", "Fox Terrier": "140", "Foxhound": "141", "French Brittany": "836", "French Bulldog": "358", "French Mastiff": "613", "Galgo Spanish Greyhound": "359", "German Pinscher": "360", "German Shepherd Dog": "142", "German Shorthaired Pointer": "143", "German Spitz": "361", "German Wirehaired Pointer": "144", "Giant Schnauzer": "363", "Glen of Imaal Terrier": "364", "Golden Retriever": "145", "Gordon Setter": "146", "Great Dane": "147", "Great Pyrenees": "148", "Greater Swiss Mountain Dog": "149", "Greyhound": "150", "Halden Hound (Haldenstrover)": "614", "Harrier": "367", "Havanese": "368", "Hollandse Tulphond": "741", "Hound": "151", "Hovawart": "369", "Husky": "152", "Ibizan Hound": "371", "Illyrian Sheepdog": "372", "Irish Setter": "153", "Irish Terrier": "373", "Irish Water Spaniel": "374", "Irish Wolfhound": "154", "Italian Greyhound": "155", "Italian Mastiff": "615", "Italian Spinone": "156", "Jack Russell Terrier": "157", "Jack Russell Terrier (Parson Russell Terrier)": "753", "Japanese Chin": "158", "Jindo (Korean)": "159", "Kai Dog": "375", "Karelian Bear Dog": "376", "Keeshond": "160", "Kerry Blue Terrier": "377", "Kishu": "378", "Klee Kai": "379", "Komondor": "380", "Kuvasz": "161", "Kyi Leo": "381", "Labrador Retriever": "162", "Retriever, Labrador": "162","Lakeland Terrier": "382", "Lancashire Heeler": "383", "Leonberger": "164", "Lhasa Apso": "163", "L\u00f6wchen": "384", "Maltese": "165", "Manchester Terrier": "166", "Maremma Sheepdog": "385", "Markiesje": "740", "Mastiff": "167", "McNab": "387", "Mexican Hairless": "616", "Miniature Bull Terrier": "736", "Miniature Pinscher": "168", "Miniature Schnauzer": "586", "Mountain Cur": "388", "Mountain Dog": "169", "Munsterlander": "389", "Neapolitan Mastiff": "170", "New Guinea Singing Dog": "390", "Newfoundland Dog": "171", "Norfolk Terrier": "392", "Norwegian Buhund": "394", "Norwegian Elkhound": "172", "Norwegian Lundehund": "395", "Norwich Terrier": "393", "Nova Scotia Duck-Tolling Retriever": "396", "Old English Sheepdog": "173", "Otterhound": "174", "Papillon": "175", "Parson Russell Terrier": "738", "Patterdale Terrier (Fell Terrier)": "397", "Pekingese": "177", "Pembroke Welsh Corgi": "585", "Peruvian Inca Orchid": "398", "Petit Basset Griffon Vendeen": "176", "Pharaoh Hound": "178", "Picardy Shepherd": "959", "Pit Bull Terrier": "179","Terrier, Pit Bull": "179", "Plott Hound": "400", "Podengo Portugueso": "401", "Pointer": "180", "Polish Lowland Sheepdog": "181", "Pomeranian": "182", "Poodle (Miniature)": "737", "Poodle (Standard)": "415", "Poodle (T-Cup)": "621", "Poodle (Toy)": "587", "Poodle (unknown type)": "183", "Portuguese Water Dog": "184", "Presa Canario": "404", "Pug": "185", "Puli": "405", "Pumi": "406", "Queensland Heeler": "617", "Rat Terrier": "186", "Red Heeler": "588", "Redbone Coonhound": "407", "Retriever": "187", "Rhodesian Ridgeback": "188", "Rottweiler": "189", "Russian Wolfhound": "618", "Saarlooswolfhond": "589", "Saint Bernard": "191", "Saluki": "408", "Saluki Greyhound": "190", "Samoyed": "192", "Schiller Hound": "619", "Schipperke": "193", "Schnauzer": "194", "Scottish Deerhound": "409", "Scottish Terrier Scottie": "195", "Sealyham Terrier": "410", "Setter": "196", "Shar Pei": "197", "Sheep Dog": "198", "Shepherd": "411", "Shetland Sheepdog Sheltie": "199", "Shiba Inu": "200", "Shih Tzu": "201", "Siberian Husky": "202", "Silky Terrier": "203", "Skye Terrier": "413", "Sloughi": "414", "Smooth Collie": "976", "Smooth Fox Terrier": "204", "Soft-Coated Wheaten Terrier": "590", "South Russian Ovcharka": "416", "Spaniel": "205", "Spanish Mastiff": "953", "Spinone Italiano": "739", "Spitz": "206", "Springer Spaniel": "591", "Staffordshire Bull Terrier": "207","Terrier, Staffordshire Bull": "207", "Sussex Spaniel": "620", "Swedish Vallhund": "417", "Tamaskan": "963", "Terrier": "208", "Thai Ridgeback": "418", "Tibetan Mastiff": "419", "Tibetan Spaniel": "420", "Tibetan Terrier": "209", "Tosa Inu": "421", "Toy Fox Terrier": "210", "Toy Terrier": "593", "Treeing Walker Coonhound": "211", "Vizsla": "212", "Weimaraner": "213", "Welsh Corgi": "214", "Welsh Springer Spaniel": "216", "Welsh Terrier": "215", "West Highland White Terrier Westie": "217", "Wheaten Terrier": "218", "Whippet": "219", "White German Shepherd": "220", "White Swiss Shepherd Dog (Swiss Berger)": "964", "Wire-haired Pointing Griffon": "221", "Wirehaired Fox Terrier": "222", "Wolf Dog": "223", "Xoloitzcuintle/Mexican Hairless": "424", "Yellow Labrador Retriever": "422", "Yorkshire Terrier Yorkie": "224"}
    dataToEdit.update({"animalPrimaryBreedID":findRGKey(results,catBreeds,dogBreeds,"PrimaryBreed")})

    if (results.find(".//Species").text=="Dog"):
        dataToEdit.update({"animalSecondaryBreedID":findRGKey(results,{},dogBreeds,"SecondaryBreed")})
    return dataToEdit

def editAnimal(data):
    print('edit')

#Helper function for retrieving data from petpoint
def findRGKey(results, catKeys,dogKeys,dataType):
    rgKeys ={}
    if (results.find(".//Species").text=="Cat"):
        rgKeys=catKeys
    else:
        rgKeys=dogKeys
    petPattern=results.find(".//"+dataType).text
    if (petPattern != None):
        for key in rgKeys.keys():
            if (petPattern.lower()==key.lower()):
                return rgKeys[key]
                break
        print("Could not find "+dataType+" "+petPattern+", this animal is a "+results.find(".//Species").text+". Leaving blank")
    return ""

def rgRunForMatch(resID):
    payload = {
        "token": token,
        "tokenHash": tokenHash,
        "objectType": "animals",
        "objectAction": "search",
        "search": {
            "filters": [
                {"fieldName": "animalRescueID", "operation": "equals", "criteria": resID}
            ],
            "fields": ["animalID","animalStatusID"],
        },
    }
    response = requests.post(V2_URL, json=payload)
    response.raise_for_status()
    data = response.json()
    if len(data["data"])>0:
        #returns as[internalID,statusID]
        return [data["data"][list(data["data"])[0]]['animalID'],data["data"][list(data["data"])[0]]['animalStatusID']]
    return False


def findDiscrepancies(ppData,rgData):
    absences=[]
    for pp in ppData.keys():
        foundMatch=False
        for rg in rgData.keys():
            if len(rg)> 9:
                if pp in rg:
                    foundMatch=True
                    break
            elif rg==pp:
                foundMatch=True
                break
        if foundMatch==False:
            search=rgRunForMatch(pp)
            #Search returns as the animals internal ID
            if search==False:
                absences.append(ppData[pp][1])
                #just appends the petpoint internalID
            else:
                print(ppData[pp][0]+" (rescueID: "+pp+") is marked active in Petpoint but not Rescuegroups")
    
    for rg in rgData.keys():
        foundMatch=False
        for pp in ppData.keys():
            if len(rg)> 9:
                if pp in rg:
                    foundMatch=True
                    break
            elif rg==pp:
                foundMatch=True
                break
        if foundMatch==False:
            print(rgData[rg][0]+" (rescueID: "+rg+") is in RescueGroups but either not in PetPoint or not active in Petpoint")

    return absences

def safeCreateRecord(ppID):
    data=getPPAdoptableDetails(ppID)
    if (rgRunForMatch(data["animalRescueID"]) == False):
        print('Creating record for '+data["animalName"]+' with Petpoint ID '+ppID)
        print(data)
        createAnimal(data)
    else:
        print("Record already found.")

ppData,rgData=gatherDicts()
print("DISCREPANCIES-----")
abscences=findDiscrepancies(ppData,rgData)
for id in abscences:
    safeCreateRecord(id)
if len(abscences)>0:
    print('All new records listed as pending in RescueGroups.')
else:
    print('No new records need to be made.')
#print(json.dumps(getPPAdoptableDetails("61354035"),indent=2))
