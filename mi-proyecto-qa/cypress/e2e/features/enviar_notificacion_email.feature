Feature: Probar enviar notificacion Email

  Scenario: Notificacion por email sin campo emails o enviado vacio
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso sin campo emails o enviado vacio
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 200

  Scenario: Notificacion por email con channel invalido
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso con channel invalido
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 500

  Scenario: Happy path notificacion por email con peticion valida
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso happy path
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 200