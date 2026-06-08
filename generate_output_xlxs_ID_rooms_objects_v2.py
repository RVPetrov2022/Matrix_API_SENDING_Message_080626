#####################################################################################
#  Из файл Старый фонд itp_fond.csv собираем output.xlxs
# Первый столбец - это номер комната, второй - это номер обьекта, третий - это название ЖК, четвертый - Адрес обьекта
# 20 мая 2026 г
###########################################################################################
import pandas as pd

# 1. Загружаем исходный файл (в директории лежит itp_fond.csv)
df = pd.read_csv('itp_fond.csv', sep=';')

# Очистим названия колонок от случайных пробелов
df.columns = df.columns.str.strip()

# 2. Создаем последовательную нумерацию для каждого НОВОГО ЖК
unique_jks = df['ЖК'].unique()
jk_mapping = {jk: f"id_room_{i+1}" for i, jk in enumerate(unique_jks)}

# Считаем количество уникальных ЖК
total_rooms = len(unique_jks)

# 3. Формируем новые колонки на основе правил
new_df = pd.DataFrame()
new_df[0] = df['ЖК'].map(jk_mapping)
new_df[1] = 'id_object_' + df['ID объекта'].astype(str).str.strip()
new_df[2] = df['ЖК']
new_df[3] = df['Адрес объекта'].astype(str) + ' (' + df['ID объекта'].astype(str) + ')'

## 4. Сохраняем результат в новый CSV-файл
#new_df.to_csv('output.csv', sep=';', index=False, header=False, encoding='utf-8-sig')

# Красивый вывод итогов в консоль
#print("*" * 50)
#print("Обработка файла успешно завершена!")
#print(f"Всего создано уникальных ЖК (id_room): {total_rooms}")
#print("Итоговый файл сохранен как: output.csv")
#print("*" * 50)


########################################################
# 4. Сохраняем результат в новый EXCEL-файл (.xlsx)
# index=False убирает лишнюю нумерацию строк от Pandas
# header=False отключает вывод технических названий колонок (0, 1, 2, 3)
new_df.to_excel('output.xlsx', index=False, header=False)

# Красивый вывод итогов в консоль
print("*" * 50)
print("Обработка файла успешно завершена!")
print(f"Всего создано уникальных ЖК (id_room): {total_rooms}")
print("Итоговый файл сохранен как: output.xlsx")
print("*" * 50)
