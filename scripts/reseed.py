import subprocess

clean_favorites = [
    'SALUKI', 'LILDRUGHILL', 'cold carti', 'Дора', 'Toxi$', 'GONE.Fludd', 
    'huzzy b', 'DooMee', 'YUNGWAY', 'aikko', 'luvdakash', 'VILLIAN', 
    'GLAM GO!', 'IROH', 'CAKEBOY', 'Flipper Floyd', 'навздохе', 'КРЕСТ', 
    'Криспи', 'вышел покурить', 'ЛСП', 'SODA LUV', 'MAYOT', 'PLOHOYPAREN', 
    'ILLENIUM', 'Travis Scott', '21 Savage', 'Juice WRLD', 'Kanye West', 'Ye', 
    'midwxst', '2hollis', '17 SEVENTEEN', '17 SVNTN', 'CUPSIZE', 'Sqwore', 
    'Куок', 'гнилаялирика', 'голодный', 'паранойя', 'тёмный принц', 'Мэйби Бэйби', 
    'Платина', 'Lida', 'pyrokinesis', 'FORTUNA 812', 'CODE80', 'PINQ', 'unki', 
    'ТРАВМА', 'ХЛЕБ', 'Слава КПСС', 'Marshmello', 'Metro Boomin'
]

pg = subprocess.check_output('docker ps -q -f name=postgres | head -n 1', shell=True).decode().strip()
subprocess.run(f'docker exec -i {pg} psql -U n8n -d n8n -c "TRUNCATE TABLE artists;"', shell=True)

for a in set(clean_favorites):
    escaped = a.replace("'", "''")
    cmd = f"docker exec -i {pg} psql -U n8n -d n8n -c \"INSERT INTO artists (name) VALUES ('{escaped}');\""
    subprocess.run(cmd, shell=True)

count = subprocess.check_output(f"docker exec -i {pg} psql -U n8n -d n8n -c 'SELECT COUNT(*) FROM artists;'", shell=True).decode()
print("Postgres artists count:\n", count)
