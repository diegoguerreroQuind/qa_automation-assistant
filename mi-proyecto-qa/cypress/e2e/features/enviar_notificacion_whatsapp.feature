Feature: Probar enviar notificacion Whatsapp
  Scenario: Ejecutar exitosamente enviar notificacion Whatsapp
    Given que tengo los datos para 'enviar notificacion Whatsapp'
    When envío la petición hacia 'enviar notificacion Whatsapp'
    Then el código de respuesta para 'enviar notificacion Whatsapp' debe ser exitoso