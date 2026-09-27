import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

def main():
    print("====================================================")
    print("   AUTOMAZIONE CARICAMENTO DOCUMENTAZIONE SUEV     ")
    print("====================================================")
    
    # Percorso del file da caricare
    file_path = "/Users/zava/.openclaw/workspace/Documento_SCIA_Milano_Oltre1000.md"
    if not os.path.exists(file_path):
        print(f"Errore: il file {file_path} non esiste nel workspace.")
        sys.exit(1)
        
    print(f"File pronto per l'invio: {file_path}")
    
    # Configurazione di Chrome
    options = Options()
    options.headless = False # Headful per permettere login e MFA
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    
    print("\nAvvio di Google Chrome sul tuo schermo...")
    driver = webdriver.Chrome(options=options)
    
    try:
        # 1. Navigazione alla pagina di login Google
        print("Apertura pagina di login Google...")
        driver.get("https://accounts.google.com/signin")
        
        # Inserimento email
        print("Inserimento email: pianodivino@protonmail.com")
        email_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, 'identifier'))
        )
        email_input.send_keys('pianodivino@protonmail.com')
        
        # Click su "Avanti"
        next_button = driver.find_element(By.ID, 'identifierNext')
        next_button.click()
        
        print("\n--> AZIONE RICHIESTA SUL TUO SCHERMO:")
        print("1. Inserisci la tua password nella finestra di Chrome che si è aperta.")
        print("2. Completa l'eventuale verifica a due fattori (MFA).")
        print("3. Una volta completato il login, verrai reindirizzato automaticamente.")
        print("\nSto monitorando lo stato dell'accesso, non chiudere la finestra...")
        
        # Monitoraggio del login fino all'accesso a Google Drive
        logged_in = False
        timeout = 3600 # 1 ora per completare il login e MFA
        start_time = time.time()
        
        # Reindirizziamo a Google Drive se l'utente finisce sulla home di Google
        redirected_to_drive = False
        
        while time.time() - start_time < timeout:
            try:
                current_url = driver.current_url
                if current_url is None:
                    time.sleep(1)
                    continue
                    
                # Se siamo loggati e sulla pagina dell'account o altro, forziamo Google Drive
                if "myaccount.google.com" in current_url or "google.it" in current_url or "google.com" in current_url:
                    if not redirected_to_drive and "signin" not in current_url:
                        print("Login rilevato! Reindirizzamento a Google Drive...")
                        driver.get("https://drive.google.com/drive/my-drive")
                        redirected_to_drive = True
                
                if "drive.google.com" in current_url:
                    print("Accesso a Google Drive completato con successo!")
                    logged_in = True
                    break
            except Exception as e:
                # Se il browser è temporaneamente occupato in una transizione, continuiamo senza crashare
                pass
                
            time.sleep(2)
            
        if not logged_in:
            print("Timeout scaduto o login non completato. Interruzione del processo.")
            driver.quit()
            sys.exit(1)
            
        time.sleep(5) # Attendiamo il caricamento completo della dashboard di Drive
        
        # 2. Creazione della Cartella
        print("\nCreazione della cartella 'SCIA_Milano_Oltre_1000'...")
        
        # Clicchiamo sul pulsante "Nuovo"
        # Cerchiamo il pulsante "Nuovo" usando XPath per renderlo robusto (funziona sia in italiano che inglese)
        new_button_xpath = "//button[contains(., 'Nuovo') or contains(., 'New')]"
        new_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, new_button_xpath))
        )
        new_button.click()
        print("Pulsante 'Nuovo' cliccato.")
        time.sleep(2)
        
        # Clicchiamo su "Nuova cartella"
        new_folder_xpath = "//span[contains(text(), 'Nuova cartella') or contains(text(), 'New folder') or contains(text(), 'Cartella')]"
        new_folder_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, new_folder_xpath))
        )
        new_folder_option.click()
        print("Opzione 'Nuova cartella' selezionata.")
        time.sleep(2)
        
        # Inseriamo il nome della cartella nel popup
        # Troviamo l'input nel dialog
        input_xpath = "//div[@role='dialog']//input"
        folder_name_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, input_xpath))
        )
        folder_name_input.clear()
        folder_name_input.send_keys("SCIA_Milano_Oltre_1000")
        print("Nome cartella inserito.")
        time.sleep(1)
        
        # Clicchiamo su "Crea"
        create_button_xpath = "//div[@role='dialog']//button[contains(., 'Crea') or contains(., 'Create')]"
        create_button = driver.find_element(By.XPATH, create_button_xpath)
        create_button.click()
        print("Cartella creata con successo!")
        time.sleep(4) # Attendiamo la sincronizzazione e la comparsa della cartella nella lista
        
        # 3. Entriamo nella cartella appena creata
        print("\nEntrata nella cartella 'SCIA_Milano_Oltre_1000'...")
        folder_element_xpath = "//div[contains(text(), 'SCIA_Milano_Oltre_1000')]"
        folder_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, folder_element_xpath))
        )
        
        # Usiamo le ActionChains per fare doppio click ed entrare nella cartella
        actions = ActionChains(driver)
        actions.double_click(folder_element).perform()
        print("Doppio click effettuato.")
        time.sleep(4) # Attendiamo il caricamento della cartella vuota
        
        # 4. Upload del file tramite l'input di tipo file nascosto
        print("\nAvvio dell'upload del file di documentazione...")
        # Troviamo l'input di tipo file presente sulla pagina per l'upload diretto
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(file_path)
        print("Upload avviato...")
        
        # Attendiamo il completamento del caricamento (controllando che appaia la notifica o che passi del tempo)
        print("Attesa del completamento del caricamento (10 secondi)...")
        time.sleep(10)
        
        print("\n====================================================")
        print("🎉 OPERAZIONE COMPLETATA CON SUCCESSO!")
        print("Il file è stato caricato nella tua nuova cartella di Drive.")
        print("====================================================")
        
    except Exception as e:
        print(f"\nSi è verificato un errore durante l'automazione: {e}")
    finally:
        # Lasciamo aperta la finestra per qualche secondo per far vedere il risultato
        time.sleep(5)
        driver.quit()
        print("Browser chiuso.")

if __name__ == "__main__":
    main()
