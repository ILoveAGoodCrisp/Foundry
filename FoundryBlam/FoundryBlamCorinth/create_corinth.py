import os
    
corinth_dir = os.path.dirname(os.path.realpath(__file__))
main_dir = os.path.dirname(corinth_dir)
for file in os.listdir(main_dir):
    file = os.path.join(main_dir, file)
    if file.lower().endswith(".cs"):
        with open(file, 'r', encoding='utf-8') as f:
            cs = f.read()
            
        new_cs = cs.replace('using Bungie', 'using Corinth')
        corinth_file = file.replace(main_dir, corinth_dir)
        with open(corinth_file, 'w', encoding='utf-8') as f:
            f.write(new_cs)