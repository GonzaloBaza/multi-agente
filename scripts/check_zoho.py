"""Verifica qué devuelve Zoho para un email dado."""
import asyncio, sys, json
sys.path.insert(0, "/app")

async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else ""
    if not email:
        print("Uso: python check_zoho.py <email>")
        return

    print(f"Buscando: {email}\n")

    # Zoho Contacts
    try:
        from integrations.zoho.contacts import ZohoContacts
        zc = ZohoContacts()
        contact = await zc.search_by_email_with_full_profile(email)
        if contact:
            print("=== ZOHO CONTACTS: ENCONTRADO ===")
            for k in ["First_Name", "Last_Name", "Email", "Profesi_n", "Especialidad",
                       "Cargo", "Lugar_de_trabajo", "Especialidad_interes"]:
                print(f"  {k}: {contact.get(k, '-')}")
            cursadas = contact.get("Formulario_de_cursada") or []
            print(f"  Cursadas: {len(cursadas)}")
        else:
            print("=== ZOHO CONTACTS: NO ENCONTRADO ===")
    except Exception as e:
        print(f"=== ZOHO CONTACTS: ERROR === {e}")

    # Area de cobranzas
    try:
        from integrations.zoho.area_cobranzas import ZohoAreaCobranzas
        adc = ZohoAreaCobranzas()
        ficha = await adc.search_by_email(email)
        if ficha and ficha.get("cobranzaId"):
            print(f"\n=== AREA COBRANZAS: ENCONTRADO ===")
            print(f"  Alumno: {ficha.get('alumno')}")
            print(f"  Saldo pendiente: {ficha.get('saldoPendiente')}")
            print(f"  Estado mora: {ficha.get('estadoMora')}")
        else:
            print("\n=== AREA COBRANZAS: NO ENCONTRADO ===")
    except Exception as e:
        print(f"\n=== AREA COBRANZAS: ERROR === {e}")

    # Supabase
    try:
        from integrations.supabase_client import get_customer_profile
        sb = await get_customer_profile(email)
        if sb:
            print(f"\n=== SUPABASE: ENCONTRADO ===")
            print(f"  {json.dumps(sb, default=str, indent=2)}")
        else:
            print("\n=== SUPABASE: NO ENCONTRADO ===")
    except Exception as e:
        print(f"\n=== SUPABASE: ERROR === {e}")

asyncio.run(main())
