# MEMRISER

**Self-learning** Memrise bot with Google Translate support.
You MUST have google chrome installed!
INSTALLATION:
1. download the .zip (click ```Code``` then ```Download ZIP```)
2. unzip the .zip somewhere
3. create a .env file in the same directory
4. Add this to the .env file:<br>
   ```MEMRISE_EMAIL=<your memrise email>```<br>
   ```MEMRISE_PASSWORD=<your memrise password>```
5. Run terminal command ```pip install requirements.txt``` while in the folder where you extracted anything
6. Download the right ChromeDriver version for your browser:<br>
    1. Check your browser version by searching ```chrome://settings/help``` and reading the version number.
    2. Then, go to [ChromeDrivers](https://github.com/dreamshao/chromedriver) and download the one matching your version, with the correct system too.
    3. Add this file to PATH:<br>
       <b>Windows</b>
       1. Move chromedriver.exe to a folder, e.g., C:\WebDriver\.<br>Press Win + S, search Environment Variables, and open Edit the system environment variables.
       2. Click Environment Variables → under System variables find Path → Edit → New.
       3. Add the folder path (e.g., C:\WebDriver\) → OK all windows.
       4. Open a new Command Prompt and run:
          <br>```chromedriver --version```
          <br>If it shows the version, it’s correctly added.<br><br>
   <b>macOS / Linux</b>
      1. Move chromedriver to a folder, e.g., /usr/local/bin/.
      2. Open terminal and add it to PATH if needed:<br>```export PATH=$PATH:/usr/local/bin```
      3. To make it permanent, add the above line to your shell config (~/.bashrc, ~/.zshrc, etc.).
  




For some reason, memrise doesn't have any anti-bot things such as captchas or movement detection, so i made this :)
Let me know if there is any bugs by making an issue.











