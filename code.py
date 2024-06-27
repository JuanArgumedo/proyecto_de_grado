#Librerias utilizadas en el programa
import adafruit_logging as logging
from modbusrtu import ModBusRTU
import busio
import board
import time
import digitalio
import wifi
import socketpool
import adafruit_requests
import ssl

#Inicialización de comunicación UART para el modulo RS-485
uart = busio.UART(tx=board.GP4, rx=board.GP5, baudrate=19200)
modbus = ModBusRTU(uart)

#Definición de pines para el control de los pilotos
VERDE = digitalio.DigitalInOut(board.GP21)
VERDE.direction = digitalio.Direction.OUTPUT

ROJO = digitalio.DigitalInOut(board.GP20)
ROJO.direction = digitalio.Direction.OUTPUT

#Arreglo para guardar la variable de energía
ENERGY = []

#Rectificación de la conexión UART
try: 
    uart
except ValueError:
    print("UART no activada")
    VERDE.value = False
    ROJO.value = True
else:
    print("UART activada OK")
    VERDE.value = True
    ROJO.value = False

#Función para conexión wifi
def wifi_connect():
    ssid = "USUARIO"
    password = "CONTRASEÑA"
    try:
        wifi.radio.connect(ssid, password)
        VERDE.value = True
        ROJO.value = False
    except Exception:
        print("Error al conectar a Internet:")
        VERDE.value = False
        ROJO.value = True

#Función para consulta http
def consulta_db(query):
    socket = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(socket, ssl.create_default_context())
    url = "http://sunandenergies.com/proyectoenergia/datos.php"
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    print("Sending data...",end="")
    try:
        response = requests.post(url, headers=headers, data=query)
        print(response.text)
    except Exception as e:
        print("\nError!", e)
        VERDE.value = False
        ROJO.value = True
    print("Done!")

#Función para convertir un numero en complemento a dos
def complemento_a_dos(valor, bits=16):
    if valor & (1 << (bits - 1)):
        valor -= 1 << bits
    return valor

#Función para convinar los datos obtenidos
def combinar_datos(data_bytes):
    data_value = (data_bytes[0] << 8) | data_bytes[1]
    data_value = complemento_a_dos(data_value)
    if data_value < 0:
        data_value = abs(data_value)
    return data_value

while True:
    
    wifi_connect()
    
    #Se crean variables de tiempo para condicionar las acciones del sistema
    fecha_actual = time.localtime()
    hora = fecha_actual[3]
    minutos = fecha_actual[4]
    segundos = fecha_actual[5]
    
    #Se calcula la energía activa acumulada durante 1 hora, agregando el valor obtenido al arreglo definido anteriormente
    if minutos == 1 and segundos == 0:
        for i in range(0, 590):
            time.sleep(1.5)
            modbus.send("03", 794)
            time.sleep(1.5)
            p_activa_1 = modbus.receive()
            data_bytes_1 = p_activa_1[3:5]
            P_ACTIVA = combinar_datos(data_bytes_1) * 0.01
            ENERGY_DATA = P_ACTIVA * (5/3600)
            ENERGY.append(ENERGY_DATA)

    #Se condiciona el envío de datos a la hora exacta
    if minutos == 0 and segundos == 0:
        
        #Se suman todos los valores del arreglo para obtener la energía de 1 hora
        ENERGY_SEND = sum(ENERGY)
        print("Energia Activa: ", ENERGY_SEND)
        
        #Segmento para obtener el dato de potencia activa del sistema
        time.sleep(2)
        modbus.send("03", 794)
        time.sleep(2)
        p_activa_2 = modbus.receive()
        data_bytes_2 = p_activa_2[3:5]
        P_ACTIVA_SEND = combinar_datos(data_bytes_2) * 0.01
        print("P ACTIVA: ", P_ACTIVA_SEND)

        #Segmento para obtener el dato de potencia activa del sistema
        time.sleep(2)
        modbus.send("03", 802)
        time.sleep(2)
        p_reactiva = modbus.receive()
        print(p_reactiva)
        data_bytes_3 = p_reactiva[3:5]
        P_REACTIVA_SEND = combinar_datos(data_bytes_3) * 0.01
        print("P REACTIVA: ", P_REACTIVA_SEND)
        
        #Se configura una cadena de texto con las variables obtenidas
        DATA_SEND = "energia="+str(ENERGY_SEND)+"&p_activa="+str(P_ACTIVA_SEND)+"&p_reactiva="+str(P_REACTIVA_SEND)
        print(DATA_SEND)
        #Se utiliza la función de consulta para enviar los datos a la base de datos web
        consulta_db(DATA_SEND)
        #Se eliminan los valores del arreglo de energía para medir la siguiente hora
        ENERGY.clear()
    
    
