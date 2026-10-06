import mysql.connector

try:
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='campusshield')
    cursor = conn.cursor()
    
    print("MySQL Connection: SUCCESS")
    print("=" * 60)
    
    # 1. Total colleges count
    cursor.execute('SELECT COUNT(*) FROM colleges')
    total_colleges = cursor.fetchone()[0]
    print(f"1. Total colleges: {total_colleges}")
    
    # 2. List all colleges
    print("\n2. All colleges (id, name, code, is_active):")
    cursor.execute('SELECT id, name, code, is_active FROM colleges ORDER BY id')
    all_colleges = cursor.fetchall()
    for row in all_colleges:
        print(f"   ID: {row[0]}, Name: {row[1]}, Code: {row[2]}, Active: {row[3]}")
    
    # 3. Original colleges (IDs 1-5)
    print("\n3. Original colleges (IDs 1-5):")
    cursor.execute('SELECT id, name, code, is_active FROM colleges WHERE id BETWEEN 1 AND 5 ORDER BY id')
    original_colleges = cursor.fetchall()
    for row in original_colleges:
        print(f"   ID: {row[0]}, Name: {row[1]}, Code: {row[2]}, Active: {row[3]}")
    
    # 4. Newly added colleges (IDs 6+)
    print("\n4. Newly added colleges (IDs 6+):")
    cursor.execute('SELECT id, name, code, is_active FROM colleges WHERE id >= 6 ORDER BY id')
    new_colleges = cursor.fetchall()
    for row in new_colleges:
        print(f"   ID: {row[0]}, Name: {row[1]}, Code: {row[2]}, Active: {row[3]}")
    
    # 5. Duplicate college names check
    print("\n5. Duplicate college names check:")
    cursor.execute('SELECT name, COUNT(*) as count FROM colleges GROUP BY name HAVING count > 1')
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"   FOUND DUPLICATES: {duplicates}")
    else:
        print("   No duplicate college names found")
    
    # 6. Duplicate college codes check
    print("\n6. Duplicate college codes check:")
    cursor.execute('SELECT code, COUNT(*) as count FROM colleges GROUP BY code HAVING count > 1')
    code_duplicates = cursor.fetchall()
    if code_duplicates:
        print(f"   FOUND DUPLICATES: {code_duplicates}")
    else:
        print("   No duplicate college codes found")
    
    # 7. New colleges active status
    print("\n7. New colleges active status (IDs 6+):")
    cursor.execute('SELECT id, name, is_active FROM colleges WHERE id >= 6')
    new_active_check = cursor.fetchall()
    all_active = all(row[2] == 1 for row in new_active_check)
    print(f"   All new colleges active: {all_active}")
    for row in new_active_check:
        print(f"   ID: {row[0]}, Name: {row[1]}, Active: {row[2]}")
    
    # 8. Existing users count
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    print(f"\n8. Total users: {total_users}")
    
    # 9. Check users.college_id values were not changed
    print("\n9. Users college_id values check:")
    cursor.execute('SELECT id, name, college_id FROM users ORDER BY id LIMIT 10')
    users_sample = cursor.fetchall()
    for row in users_sample:
        print(f"   User ID: {row[0]}, Name: {row[1]}, College ID: {row[2]}")
    
    # 10. Marks count
    cursor.execute('SELECT COUNT(*) FROM marks')
    total_marks = cursor.fetchone()[0]
    print(f"\n10. Total marks: {total_marks}")
    
    # 11. Attendance count
    cursor.execute('SELECT COUNT(*) FROM attendance')
    total_attendance = cursor.fetchone()[0]
    print(f"\n11. Total attendance: {total_attendance}")
    
    conn.close()
    
except mysql.connector.Error as e:
    print(f"MySQL Connection Error: {e}")
    print("VERIFICATION STOPPED - MySQL unavailable")
